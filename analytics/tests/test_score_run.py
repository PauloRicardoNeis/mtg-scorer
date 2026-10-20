"""Score-run files are reproducible, attributable and never silently replaced (SYNTHETIC)."""

import json
import sys
from pathlib import Path

import pytest
from synthetic_topdeck import BOLT, COUNTERSPELL, ISLAND, open_event, save, weekly_event

from mtg_scorer import SCORE_METHODS, MaxRatioMethod, cli
from mtg_scorer.ingest.topdeck import read_saved_responses
from mtg_scorer.publish.score_run import (
    ATTRIBUTION,
    POPULATION_RULE,
    SCHEMA_VERSION,
    build_score_run,
    load_cohort_rules,
    score_topdeck,
    write_score_run,
)
from mtg_scorer.tournament_features import CohortRules

COHORT_FILE = Path(__file__).resolve().parents[1] / "cohorts/topdeck-modern-2026-03-to-08.json"
RULES = CohortRules(
    version="synthetic-cohort-v1",
    format_name="Modern",
    starts_on="2026-03-01",
    ends_before="2026-09-01",
)


def saved(tmp_path, name="saved"):
    return save(tmp_path / name, {"search.json": [open_event(), weekly_event()]})


def document(tmp_path, methods=SCORE_METHODS):
    return build_score_run(read_saved_responses(saved(tmp_path)), RULES, methods)


def scores(run, output):
    return {score["card_id"]: score["values"][output] for score in run["scores"]}


def test_a_run_records_its_complete_computational_identity(tmp_path) -> None:
    run = document(tmp_path)

    assert run["schema_version"] == SCHEMA_VERSION
    assert run["score_run_id"].startswith("scores-")
    assert run["dataset_snapshot_id"].startswith("topdeck-")
    assert run["cohort_rules_hash"] == RULES.fingerprint
    assert run["population_rule"] == POPULATION_RULE
    assert run["method_identities"] == [
        [method.method_id, method.version, method.config_hash] for method in SCORE_METHODS
    ]
    assert run["attribution"] == ATTRIBUTION


def test_the_same_inputs_give_the_same_run_identity(tmp_path) -> None:
    assert document(tmp_path)["score_run_id"] == document(tmp_path / "again")["score_run_id"]


def test_the_run_identity_changes_with_the_methods(tmp_path) -> None:
    only_volume = document(tmp_path, methods=(MaxRatioMethod(),))

    assert only_volume["score_run_id"] != document(tmp_path / "again")["score_run_id"]
    assert [run["method_id"] for run in only_volume["runs"]] == ["max-ratio"]


def test_the_cohort_summary_keeps_events_exclusions_and_totals(tmp_path) -> None:
    cohort = document(tmp_path)["cohort"]

    assert [event["source_event_id"] for event in cohort["events"]] == [
        "synthetic-open",
        "synthetic-weekly",
    ]
    assert cohort["events"][0] == {
        "source_event_id": "synthetic-open",
        "occurred_on": "2026-03-10",
        "players": 4,
        "decklists": 3,
        "top_cut_size": 2,
        "top_cut_basis": "standing_order",
    }
    assert cohort["totals"] == {
        "events": 2,
        "players": 6,
        "decks": 5,
        "incomplete_decks_excluded": 0,
        "top_cut_players": 2,
        "top_cut_decks": 2,
        "quarantined_card_lines_in_source": 0,
        "team_events_skipped_in_source": 0,
        "top_cut_known_decks": 3,
        "record_decks": 5,
        "matches": 5,
    }
    assert cohort["rules"]["hash"] == RULES.fingerprint
    assert cohort["rules"]["players_per_game"] == 2


def test_the_cohort_summary_states_the_field_baselines_trend_and_archetypes(tmp_path) -> None:
    cohort = document(tmp_path)["cohort"]

    assert cohort["performance"] == {
        "players_per_game": 2,
        "record": {"decks": 5, "wins": 7, "losses": 4, "draws": 0},
        "win_rate": 0.6364,
        "top_cut_rate": 0.6667,
    }
    # A 184-day window splits into twelve 16-day periods; the events fall in two of them.
    assert cohort["series"] == {
        "starts_on": "2026-02-21",
        "period_days": 16,
        "decks": [0, 3, 2] + [0] * 9,
    }
    assert [(a["label"], a["deck_count"]) for a in cohort["archetypes"]] == [
        ("Burn", 2),
        ("Control", 3),
    ]
    assert cohort["archetypes"][1]["core_cards"] == [COUNTERSPELL]


def test_basic_lands_are_described_but_not_scored(tmp_path) -> None:
    run = document(tmp_path)
    cards = {card["oracle_id"]: card for card in run["cards"]}

    assert cards[ISLAND]["scored"] is False
    assert run["population"]["excluded_cards"] == ["Island"]
    assert run["population"]["scored_cards"] == 2
    assert all(ISLAND not in scores(each, each["outputs"][0]) for each in run["runs"])


def test_cards_carry_their_usage_with_denominators(tmp_path) -> None:
    bolt = next(card for card in document(tmp_path)["cards"] if card["oracle_id"] == BOLT)

    assert bolt == {
        "oracle_id": BOLT,
        "name": "Bolt",
        "scored": True,
        "deck_count": 3,
        "event_count": 2,
        "top_cut_count": 2,
        "top_cut_known_decks": 2,
        "archetype": {"label": "Burn", "deck_count": 2, "labelled_deck_count": 3},
        "archetypes": {
            "distinct": 2,
            "top": [{"label": "Burn", "deck_count": 2}, {"label": "Control", "deck_count": 1}],
        },
        "mainboard_copies": 10,
        "record": {"decks": 3, "wins": 6, "losses": 1, "draws": 0},
        "performance": {
            "win_rate": 0.8571,
            "win_rate_delta": 0.2208,
            "win_rate_ci95": 0.2592,
            "top_cut_lift": 1.5,
            "share_delta": None,
        },
        "series": [0, 2, 1] + [0] * 9,
    }


def test_every_registered_method_scores_the_population(tmp_path) -> None:
    runs = {run["method_id"]: run for run in document(tmp_path)["runs"]}

    assert set(runs) == set(SCORE_METHODS.method_ids)
    assert scores(runs["max-ratio"], "max_ratio") == {BOLT: 100.0, COUNTERSPELL: 100.0}
    assert runs["max-ratio"]["label"] == MaxRatioMethod.label
    assert set(scores(runs["foundation"], "staple")) == {BOLT, COUNTERSPELL}
    assert scores(runs["constructed-score"], "score") == {BOLT: 75.0, COUNTERSPELL: 25.0}
    # Every Counterspell deck is Control; Bolt splits between Burn and Control.
    assert scores(runs["signature-score"], "score") == {BOLT: 25.0, COUNTERSPELL: 75.0}


def test_writing_names_the_file_after_its_identity(tmp_path) -> None:
    run = document(tmp_path)
    path = write_score_run(run, tmp_path / "runs")

    assert path.name == f"{run['score_run_id']}.json"
    assert json.loads(path.read_bytes()) == json.loads(json.dumps(run))
    assert [p.name for p in (tmp_path / "runs").iterdir()] == [path.name]


def test_rewriting_identical_results_reuses_the_file(tmp_path) -> None:
    run = document(tmp_path)
    first = write_score_run(run, tmp_path / "runs")
    copy_time = "2026-01-01T00:00:00+00:00"
    copied = {**run, "raw_files": [{**run["raw_files"][0], "retrieved_at": copy_time}]}

    assert write_score_run(copied, tmp_path / "runs") == first


def test_different_results_under_the_same_identity_are_refused(tmp_path) -> None:
    run = document(tmp_path)
    write_score_run(run, tmp_path / "runs")
    changed = {**run, "attribution": "A different credit"}

    with pytest.raises(ValueError, match="different results for the same identity"):
        write_score_run(changed, tmp_path / "runs")


def test_the_committed_modern_cohort_rules_load() -> None:
    rules = load_cohort_rules(COHORT_FILE)

    assert (rules.format_name, rules.starts_on, rules.ends_before) == (
        "Modern",
        "2026-03-01",
        "2026-09-01",
    )
    assert rules.min_decklist_coverage == 0.5
    assert {event.source_event_id for event in rules.excluded_events} == {
        "impact-returns-26-sunday-modern-2015",
        "test-new-la",
    }


def test_score_topdeck_reads_scores_and_writes_in_one_step(tmp_path) -> None:
    path = score_topdeck(saved(tmp_path), COHORT_FILE, tmp_path / "runs")

    assert json.loads(path.read_bytes())["cohort"]["totals"]["decks"] == 5


def test_the_cli_prints_the_written_run_file(monkeypatch, capsys, tmp_path) -> None:
    arguments = [
        "mtg-scorer",
        "score-topdeck",
        "--source-dir",
        str(saved(tmp_path)),
        "--cohort",
        str(COHORT_FILE),
        "--output-root",
        str(tmp_path / "runs"),
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    cli.main()

    printed = Path(capsys.readouterr().out.strip())
    assert printed.parent == tmp_path / "runs"
    assert printed.name.startswith("scores-")


def test_the_database_header_counts_every_row_it_will_load(tmp_path) -> None:
    from mtg_scorer.publish.score_postgres import score_run_header
    from mtg_scorer.publish.score_run import results_sha256

    run = document(tmp_path)
    header = score_run_header(run)

    assert header["format_name"] == "Modern"
    assert (header["window_starts_on"], header["window_ends_before"]) == (
        "2026-03-01",
        "2026-09-01",
    )
    assert header["row_counts"] == {
        "cards": 3,
        "methods": 4,
        "scores": 18,
        "inputs": 24,
        "card_archetypes": 5,
        "archetypes": 2,
    }
    assert header["results_sha256"] == results_sha256(run)
    assert header["summary"]["cohort"] == run["cohort"]
