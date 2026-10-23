"""Overall-run files are checked before writing or publishing, and pool only what adds up
across formats (SYNTHETIC)."""

import copy
import json

import pytest
from jsonschema import Draft202012Validator, ValidationError
from synthetic_topdeck import BOLT, deck, event, open_event, row, save, weekly_event

from mtg_scorer.ingest.topdeck import read_saved_responses
from mtg_scorer.publish import overall_run
from mtg_scorer.publish.overall_run import FORMAT_NAME, active_run_files, build_overall_run
from mtg_scorer.publish.score_postgres import publish_score_run, score_run_header
from mtg_scorer.publish.score_run import build_score_run
from mtg_scorer.publish.score_validation import OVERALL_SCHEMA, validate_overall_run
from mtg_scorer.scoring import FormatGrades
from mtg_scorer.tournament_features import CohortRules

BURN = deck({"Bolt": (BOLT, 4)})


def component(tmp_path, fmt, events):
    directory = save(tmp_path / fmt, {"search.json": events})
    rules = CohortRules(
        version="synthetic-overall-v1",
        format_name=fmt,
        starts_on="2026-03-01",
        ends_before="2026-09-01",
    )
    return build_score_run(read_saved_responses(directory), rules)


@pytest.fixture
def components(tmp_path):
    modern = component(tmp_path, "Modern", [open_event(), weekly_event()])
    legacy = component(
        tmp_path,
        "Legacy",
        [
            event(
                "synthetic-legacy",
                [row(2, deck_obj=BURN), row(1, 1, deck_obj=BURN), row(0, 2)],
                top_cut=1,
                fmt="Legacy",
            )
        ],
    )
    return [modern, legacy]


@pytest.fixture
def document(components):
    return build_overall_run(components)


def test_the_schema_is_a_valid_draft_2020_12_schema() -> None:
    Draft202012Validator.check_schema(OVERALL_SCHEMA)


def test_top_cut_lift_pools_top_cuts_made_over_those_the_fields_expect(
    components, document
) -> None:
    made = expected = 0.0
    for run in components:
        bolt = next(card for card in run["cards"] if card["oracle_id"] == BOLT)
        made += bolt["top_cut_count"]
        expected += bolt["top_cut_known_decks"] * run["cohort"]["performance"]["top_cut_rate"]
    pooled = next(card for card in document["cards"] if card["oracle_id"] == BOLT)

    assert pooled["performance"]["top_cut_lift"] == pytest.approx(made / expected, abs=1e-4)


def bolt(run):
    return next(card for card in run["cards"] if card["oracle_id"] == BOLT)


def drop_a_score(run):
    run["runs"][0]["scores"].pop()


def stale_identity(run):
    run["method_identities"][0][1] = "overall-grade-v0"


def duplicate_method(run):
    run["runs"].append(copy.deepcopy(run["runs"][0]))
    run["method_identities"].append(run["method_identities"][0])


@pytest.mark.parametrize(
    ("change", "error"),
    [
        pytest.param(
            lambda run: run.update(schema_version="score-run-file-v2"),
            ValidationError,
            id="version",
        ),
        pytest.param(
            lambda run: bolt(run).update(scored=False), ValidationError, id="unscored-card"
        ),
        pytest.param(
            lambda run: bolt(run)["performance"].update(win_rate=0.5),
            ValidationError,
            id="pooled-win-rate",
        ),
        pytest.param(
            lambda run: run["components"][1].update(
                format_name=run["components"][0]["format_name"]
            ),
            ValueError,
            id="duplicate-format",
        ),
        pytest.param(
            lambda run: run["components"][0].update(format_name=FORMAT_NAME),
            ValueError,
            id="overall-as-component",
        ),
        pytest.param(lambda run: run["totals"].update(formats=3), ValueError, id="format-total"),
        pytest.param(
            lambda run: run["cards"].append(copy.deepcopy(bolt(run))),
            ValueError,
            id="duplicate-card",
        ),
        pytest.param(
            lambda run: bolt(run).update(top_cut_count=None), ValueError, id="top-cut-unknown"
        ),
        pytest.param(
            lambda run: bolt(run).update(event_count=999), ValueError, id="events-exceed-decks"
        ),
        pytest.param(
            lambda run: bolt(run).update(formats={"Vintage": 50.0}),
            ValueError,
            id="foreign-format",
        ),
        pytest.param(
            lambda run: run["population"].update(scored_cards=1), ValueError, id="population"
        ),
        pytest.param(stale_identity, ValueError, id="method-identity"),
        pytest.param(duplicate_method, ValueError, id="duplicate-method"),
        pytest.param(drop_a_score, ValueError, id="unscored"),
        pytest.param(
            lambda run: run["runs"][0]["scores"][0]["values"].update(extra=1.0),
            ValueError,
            id="extra-output",
        ),
    ],
)
def test_malformed_overall_runs_are_rejected(document, change, error) -> None:
    validate_overall_run(document)
    broken = copy.deepcopy(document)
    change(broken)

    with pytest.raises(error):
        validate_overall_run(broken)


def test_publication_refuses_an_invalid_overall_file_before_connecting(document, tmp_path) -> None:
    broken = copy.deepcopy(document)
    broken["totals"]["formats"] = 9
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(broken), encoding="utf-8")

    with pytest.raises(ValueError, match="number of formats"):
        publish_score_run(path, "host=unreachable.invalid")


def test_the_header_stores_totals_where_a_format_run_keeps_its_cohort(document) -> None:
    header = score_run_header(document)

    assert header["format_name"] == FORMAT_NAME
    assert header["summary"]["cohort"] == {"totals": document["totals"]}
    assert header["summary"]["components"] == document["components"]
    assert header["row_counts"]["archetypes"] == 0
    assert header["row_counts"]["card_archetypes"] == 0
    assert header["row_counts"]["cards"] == len(document["cards"])


def test_components_must_share_one_source(components) -> None:
    components[1]["source"] = "another-source"

    with pytest.raises(ValueError, match="one source"):
        build_overall_run(components)


def test_at_least_one_component_must_have_graded_cards(tmp_path) -> None:
    empty = component(tmp_path, "Pioneer", [event("synthetic-empty", [row(1)], fmt="Pioneer")])

    with pytest.raises(ValueError, match="no component has graded cards"):
        build_overall_run([empty])


@pytest.mark.parametrize(
    ("name", "decks", "message"),
    [(" ", 10, "format_name cannot be blank"), ("Modern", -1, "decks cannot be negative")],
)
def test_format_grades_need_a_name_and_a_deck_count(name, decks, message) -> None:
    with pytest.raises(ValueError, match=message):
        FormatGrades(name, decks, {})


class FakeConnection:
    def __init__(self, ids):
        self.ids = ids
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params):
        self.statements.append((statement, params))
        return [(run_id,) for run_id in self.ids]


def test_active_run_files_are_every_active_format_run_but_the_overall(
    tmp_path, monkeypatch
) -> None:
    connection = FakeConnection(["scores-a", "scores-b"])
    monkeypatch.setattr("psycopg.connect", lambda dsn: connection)
    for run_id in ("scores-a", "scores-b"):
        (tmp_path / f"{run_id}.json").write_text("{}", encoding="utf-8")

    files = active_run_files("dsn", tmp_path)

    assert [path.name for path in files] == ["scores-a.json", "scores-b.json"]
    assert connection.statements[0][1] == (overall_run.FORMAT_NAME,)


def test_an_active_run_without_its_file_is_reported(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("psycopg.connect", lambda dsn: FakeConnection(["scores-missing"]))

    with pytest.raises(FileNotFoundError, match=r"scores-missing\.json"):
        active_run_files("dsn", tmp_path)
