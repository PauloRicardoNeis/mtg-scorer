"""Overall-run files combine one run per format into an attributable whole (SYNTHETIC)."""

import json
import sys
from pathlib import Path

import pytest
from synthetic_topdeck import BOLT, COUNTERSPELL, ISLAND, deck, event, row, save

from mtg_scorer import cli
from mtg_scorer.ingest.topdeck import read_saved_responses
from mtg_scorer.publish.overall_run import (
    FORMAT_NAME,
    POPULATION_RULE,
    SCHEMA_VERSION,
    build_overall_run,
    score_overall,
)
from mtg_scorer.publish.score_run import build_score_run, write_score_run
from mtg_scorer.publish.score_validation import validate_overall_run
from mtg_scorer.scoring import MaxRatioMethod, OverallMethod
from mtg_scorer.tournament_features import CohortRules

BURN = deck({"Bolt": (BOLT, 4), "Island": (ISLAND, 10)})
CONTROL = deck({"Bolt": (BOLT, 2), "Counterspell": (COUNTERSPELL, 4)})


def component(tmp_path, fmt, rows, *, players_per_game=2, starts_on="2026-03-01", **options):
    directory = save(tmp_path / fmt, {"search.json": [event(f"synthetic-{fmt}", rows, fmt=fmt)]})
    rules = CohortRules(
        version="synthetic-overall-v1",
        format_name=fmt,
        starts_on=starts_on,
        ends_before="2026-09-01",
        players_per_game=players_per_game,
    )
    return build_score_run(read_saved_responses(directory), rules, **options)


def components(tmp_path):
    modern = component(
        tmp_path,
        "Modern",
        [row(3, deck_obj=BURN), row(2, 1, deck_obj=CONTROL), row(0, 3, deck_obj=CONTROL)],
    )
    legacy = component(
        tmp_path,
        "Legacy",
        [row(2, 1, deck_obj=CONTROL), row(1, 2, deck_obj=BURN)],
        starts_on="2026-01-01",
    )
    return [modern, legacy]


def cards(run):
    return {card["name"]: card for card in run["cards"]}


def test_an_overall_run_records_its_components_and_identity(tmp_path) -> None:
    modern, legacy = components(tmp_path)
    run = build_overall_run([modern, legacy])

    validate_overall_run(run)
    assert run["schema_version"] == SCHEMA_VERSION
    assert run["format_name"] == FORMAT_NAME
    assert run["population_rule"] == POPULATION_RULE
    assert [c["format_name"] for c in run["components"]] == ["Legacy", "Modern"]
    assert {c["score_run_id"] for c in run["components"]} == {
        modern["score_run_id"],
        legacy["score_run_id"],
    }
    assert (run["window_starts_on"], run["window_ends_before"]) == ("2026-01-01", "2026-09-01")
    assert run["totals"]["formats"] == 2
    assert run["totals"]["decks"] == 5
    method = OverallMethod()
    assert run["method_identities"] == [[method.method_id, method.version, method.config_hash]]


def test_the_same_components_in_any_order_give_the_same_run(tmp_path) -> None:
    modern, legacy = components(tmp_path)

    assert build_overall_run([modern, legacy]) == build_overall_run([legacy, modern])


def test_usage_is_pooled_and_each_format_grade_is_kept(tmp_path) -> None:
    run = build_overall_run(components(tmp_path))
    bolt = cards(run)["Bolt"]

    assert bolt["deck_count"] == 5
    assert bolt["record"] == {"decks": 5, "wins": 8, "losses": 7, "draws": 0}
    assert set(bolt["formats"]) == {"Modern", "Legacy"}
    # No format grades basic lands, so the overall run has none.
    assert "Island" not in cards(run)


def test_win_rates_are_not_pooled_across_formats_but_their_gaps_are(tmp_path) -> None:
    modern, legacy = components(tmp_path)
    run = build_overall_run([modern, legacy])
    performance = cards(run)["Counterspell"]["performance"]
    gaps = [
        (card["performance"]["win_rate_delta"], sum(card["record"][k] for k in ("wins", "losses")))
        for document in (modern, legacy)
        for card in document["cards"]
        if card["name"] == "Counterspell"
    ]

    assert performance["win_rate"] is None
    assert performance["win_rate_delta"] == pytest.approx(
        sum(delta * games for delta, games in gaps) / sum(games for _, games in gaps), abs=1e-4
    )


def test_components_from_different_code_versions_are_all_recorded(tmp_path) -> None:
    modern, legacy = components(tmp_path)
    legacy["parser_version"] = "a-parser"

    run = build_overall_run([modern, legacy])

    assert run["parser_version"] == f"a-parser+{modern['parser_version']}"
    assert run["feature_pipeline_version"] == modern["feature_pipeline_version"]


def test_every_component_must_hold_the_combined_method(tmp_path) -> None:
    modern = component(tmp_path, "Modern", [row(1, deck_obj=BURN)], methods=[MaxRatioMethod()])

    with pytest.raises(ValueError, match="no constructed-score scores"):
        build_overall_run([modern])


def test_a_format_cannot_be_combined_twice(tmp_path) -> None:
    modern, _ = components(tmp_path)

    with pytest.raises(ValueError, match="only once"):
        build_overall_run([modern, modern])


def test_components_without_decklists_are_left_out(tmp_path) -> None:
    modern, _ = components(tmp_path)
    empty = component(tmp_path, "Pioneer", [row(1)])

    run = build_overall_run([modern, empty])

    assert [c["format_name"] for c in run["components"]] == ["Modern"]


def test_score_overall_writes_a_reproducible_file(tmp_path) -> None:
    files = [write_score_run(document, tmp_path / "runs") for document in components(tmp_path)]

    first = score_overall(files, tmp_path / "overall")
    again = score_overall(list(reversed(files)), tmp_path / "overall")

    assert first == again
    assert json.loads(first.read_bytes())["score_run_id"] == first.stem


def test_the_cli_combines_run_files(tmp_path, monkeypatch, capsys) -> None:
    files = [write_score_run(document, tmp_path / "runs") for document in components(tmp_path)]
    arguments = ["score-overall", "--output-root", str(tmp_path / "overall")]
    for path in files:
        arguments += ["--run-file", str(path)]
    monkeypatch.setattr(sys, "argv", ["mtg-scorer", *arguments])

    cli.main()

    written = capsys.readouterr().out.strip()
    assert json.loads(Path(written).read_bytes())["format_name"] == FORMAT_NAME
