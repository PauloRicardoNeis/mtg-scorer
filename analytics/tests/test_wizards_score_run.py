"""Saved Wizards coverage becomes an attributable score-run file (SYNTHETIC data)."""

import json
import sys
from pathlib import Path

import pytest
from synthetic_wizards import EVENT, oracle, resolver, save

from mtg_scorer import cli
from mtg_scorer.ingest import wizards
from mtg_scorer.publish.score_run import load_cohort_rules, score_wizards

COHORTS = Path(__file__).resolve().parents[1] / "cohorts"


def cohort(tmp_path, **changes):
    rules = {
        "version": "synthetic-wizards-extended-v1",
        "format_name": "Extended",
        "starts_on": "2005-01-01",
        "ends_before": "2006-01-01",
        "min_decklist_coverage": 0.5,
        **changes,
    }
    path = tmp_path / "cohort.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    return path


def test_a_run_names_the_coverage_source_parser_and_attribution(tmp_path) -> None:
    path = score_wizards([save(tmp_path)], cohort(tmp_path), tmp_path / "runs", resolver)
    run = json.loads(path.read_bytes())

    assert (run["source"], run["parser_version"], run["attribution"]) == (
        wizards.SOURCE,
        wizards.PARSER_VERSION,
        wizards.ATTRIBUTION,
    )
    assert run["dataset_snapshot_id"].startswith("wizards-")
    assert path.name == f"{run['score_run_id']}.json"


def test_the_cohort_counts_complete_decks_and_their_records(tmp_path) -> None:
    run = json.loads(
        score_wizards([save(tmp_path)], cohort(tmp_path), tmp_path / "runs", resolver).read_bytes()
    )

    (event,) = run["cohort"]["events"]
    # The saved coverage names neither the event nor a page for it.
    assert event == {
        "source_event_id": "ptsyn05",
        "name": None,
        "url": None,
        "occurred_on": "2005-10-28",
        "players": 9,
        "decklists": 7,
        "top_cut_size": 8,
        "top_cut_basis": "standing_order",
    }
    totals = run["cohort"]["totals"]
    # Ben's main deck holds an unresolved card, so six of seven decks are counted.
    assert (totals["decks"], totals["incomplete_decks_excluded"]) == (6, 1)
    assert totals["quarantined_card_lines_in_source"] == 2
    # Zed Zulu has no standing; the other five complete decks have records.
    assert totals["record_decks"] == 5
    cards = {card["name"]: card for card in run["cards"]}
    assert cards["Psychatog"]["deck_count"] == 2
    assert cards["Psychatog"]["oracle_id"] == oracle(3)
    assert cards["Psychatog"]["top_cut_count"] == 2
    assert "Pyrostatik Pillar" not in cards


def test_an_event_outside_the_window_leaves_the_cohort_empty_but_explained(tmp_path) -> None:
    run = json.loads(
        score_wizards(
            [save(tmp_path)],
            cohort(tmp_path, starts_on="2006-01-01", ends_before="2007-01-01"),
            tmp_path / "runs",
            resolver,
        ).read_bytes()
    )

    assert run["cohort"]["events"] == []
    assert run["cohort"]["excluded_events"] == [
        {"source_event_id": "ptsyn05", "reason": "outside the cohort window"}
    ]


def test_the_cli_resolves_names_in_the_catalog_it_is_given(monkeypatch, capsys, tmp_path):
    opened = []

    def fake_resolver(dsn):
        opened.append(dsn)
        return resolver

    monkeypatch.setenv("CATALOG_READ_DSN", "dbname=catalog_read")
    monkeypatch.setattr(wizards, "catalog_resolver", fake_resolver)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mtg-scorer",
            "score-wizards",
            "--source-dir",
            str(save(tmp_path)),
            "--cohort",
            str(cohort(tmp_path)),
            "--output-root",
            str(tmp_path / "runs"),
        ],
    )
    cli.main()

    printed = Path(capsys.readouterr().out.strip())
    assert printed.parent == tmp_path / "runs"
    assert opened == ["dbname=catalog_read"]


@pytest.mark.parametrize("path", sorted(COHORTS.glob("wizards-*.json")), ids=lambda p: p.stem)
def test_each_wizards_cohort_names_its_window_and_format(path) -> None:
    rules = load_cohort_rules(path)

    assert rules.version == f"{path.stem}-v1"
    first, last = path.stem.split("-")[-5:-3], path.stem.split("-")[-2:]
    assert rules.starts_on == f"{first[0]}-{first[1]}-01"
    assert rules.ends_before > f"{last[0]}-{last[1]}-01"
    assert rules.format_name.lower().replace(" ", "-") in path.stem


def test_the_saved_event_falls_in_its_cohort(tmp_path) -> None:
    rules = load_cohort_rules(COHORTS / "wizards-extended-2004-10-to-2005-10.json")

    assert rules.format_name == EVENT["format"]
    assert rules.starts_on <= EVENT["date"] < rules.ends_before


def test_a_season_cohort_scores_several_events_together(tmp_path) -> None:
    first = save(tmp_path, name="ptsyn05")
    second = save(
        tmp_path,
        event={**EVENT, "code": "mtgevent/ptsyn04", "date": "2005-02-11"},
        name="ptsyn04",
    )

    run = json.loads(
        score_wizards([first, second], cohort(tmp_path), tmp_path / "runs", resolver).read_bytes()
    )

    assert [event["source_event_id"] for event in run["cohort"]["events"]] == [
        "ptsyn04",
        "ptsyn05",
    ]
    assert run["cohort"]["totals"]["decks"] == 12
    # Both directories hold a page-res1.html; each keeps its directory in its name.
    names = [raw["name"] for raw in run["raw_files"]]
    assert {"ptsyn05/page-res1.html", "ptsyn04/page-res1.html"} <= set(names)
    assert len(names) == len(set(names))


def test_an_event_saved_twice_is_refused(tmp_path) -> None:
    with pytest.raises(ValueError, match="saved more than once: ptsyn05"):
        wizards.read_saved_events(
            [save(tmp_path, name="first"), save(tmp_path, name="again")], resolver
        )
