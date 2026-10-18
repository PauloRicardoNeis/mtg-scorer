"""Saved TopDeck responses become verified, source-independent facts (SYNTHETIC data)."""

import json
from datetime import UTC, date, datetime

import pytest
from synthetic_topdeck import (
    BOLT,
    COUNTERSPELL,
    ISLAND,
    deck,
    event,
    open_event,
    row,
    save,
    weekly_event,
)

from mtg_scorer.domain import CoverageScope
from mtg_scorer.ingest.topdeck import (
    BRACKET_RECORD,
    INCONSISTENT_ORDER,
    NO_TOP_CUT,
    PARSER_VERSION,
    STANDING_ORDER,
    read_saved_responses,
)


def read(tmp_path, *events, retrieved_at=None):
    return read_saved_responses(
        save(tmp_path / "saved", {"search.json": list(events)}, retrieved_at)
    )


def test_events_keep_independent_coverage_for_lists_standings_and_matches(tmp_path) -> None:
    snapshot = read(tmp_path, open_event(), weekly_event())
    by_id = {t.source_event_id: t for t in snapshot.tournaments}

    open_coverage = by_id["synthetic-open"].coverage
    assert open_coverage.decklists.scope is CoverageScope.PARTIAL
    assert (open_coverage.decklists.observed_count, open_coverage.decklists.expected_count) == (
        3,
        4,
    )
    assert open_coverage.standings.scope is CoverageScope.FULL_FIELD
    assert open_coverage.matches.scope is CoverageScope.UNKNOWN
    assert by_id["synthetic-weekly"].coverage.decklists.scope is CoverageScope.FULL_FIELD
    assert by_id["synthetic-open"].occurred_on == date(2026, 3, 10)
    assert by_id["synthetic-open"].player_count == 4
    assert by_id["synthetic-open"].top_cut_size == 2


def test_an_event_without_lists_has_none_coverage_not_unknown(tmp_path) -> None:
    snapshot = read(tmp_path, event("synthetic-local", [row(1), row(0, 1)]))

    assert snapshot.tournaments[0].coverage.decklists.scope is CoverageScope.NONE
    assert snapshot.decks == ()
    assert len(snapshot.standings) == 2


def test_every_player_gets_a_standing_but_only_structured_lists_become_decks(tmp_path) -> None:
    snapshot = read(tmp_path, open_event())

    assert [s.source_deck_id for s in snapshot.standings] == [
        f"synthetic-open#{position}" for position in (1, 2, 3, 4)
    ]
    assert [d.source_deck_id for d in snapshot.decks] == [
        "synthetic-open#1",
        "synthetic-open#2",
        "synthetic-open#3",
    ]
    assert (snapshot.standings[1].wins, snapshot.standings[1].losses) == (2, 1)


def test_cards_keep_mainboard_and_sideboard_copies_by_oracle_id(tmp_path) -> None:
    listed = deck(
        {"Bolt": (BOLT, 3), "Lightning Bolt": (BOLT, 1)},
        {"Counterspell": (COUNTERSPELL, 2), "Bolt": (BOLT, 1)},
    )
    snapshot = read(tmp_path, event("synthetic-merge", [row(1, deck_obj=listed)]))
    cards = {card.oracle_id: card for card in snapshot.decks[0].cards}

    assert (cards[BOLT].name, cards[BOLT].mainboard_count, cards[BOLT].sideboard_count) == (
        "Bolt",
        4,
        1,
    )
    assert (cards[COUNTERSPELL].mainboard_count, cards[COUNTERSPELL].sideboard_count) == (0, 2)
    assert snapshot.decks[0].sideboard_observed


def test_a_missing_sideboard_stays_unobserved_not_empty(tmp_path) -> None:
    snapshot = read(tmp_path, open_event())

    assert [d.sideboard_observed for d in snapshot.decks] == [True, True, False]


def test_unreadable_lines_are_quarantined_and_mark_the_mainboard_incomplete(tmp_path) -> None:
    listed = deck({"Bolt": (BOLT, 4), "Mystery": ("", 2)}, {"Odd": (ISLAND, 0)})
    snapshot = read(tmp_path, event("synthetic-broken", [row(1, deck_obj=listed)]))

    assert snapshot.quarantined_card_lines == 2
    assert snapshot.incomplete_mainboards == frozenset({"synthetic-broken#1"})
    assert not snapshot.decks[0].sideboard_observed
    assert [card.oracle_id for card in snapshot.decks[0].cards] == [BOLT]


def test_a_bad_sideboard_line_does_not_make_the_mainboard_incomplete(tmp_path) -> None:
    listed = deck({"Bolt": (BOLT, 4)}, {"Odd": (None, 1)})
    snapshot = read(tmp_path, event("synthetic-side", [row(1, deck_obj=listed)]))

    assert snapshot.incomplete_mainboards == frozenset()
    assert not snapshot.decks[0].sideboard_observed


def test_archetype_labels_are_kept_and_blank_labels_become_unknown(tmp_path) -> None:
    listed = deck({"Bolt": (BOLT, 4)})
    snapshot = read(
        tmp_path,
        event(
            "synthetic-labels",
            [row(1, deck_obj=listed, archetype=" Burn "), row(0, deck_obj=listed, archetype=" ")],
        ),
    )

    assert [d.archetype_label for d in snapshot.decks] == ["Burn", None]


def test_top_cut_comes_from_bracket_records_when_the_response_has_them(tmp_path) -> None:
    rows = [
        row(2, winsBracket=0, lossesBracket=1),
        row(3, winsBracket=1, lossesBracket=0),
        row(1, winsBracket=0, lossesBracket=0),
    ]
    snapshot = read(tmp_path, event("synthetic-bracket", rows, top_cut=2))

    assert snapshot.top_cut_basis["synthetic-bracket"] == BRACKET_RECORD
    assert [s.made_top_cut for s in snapshot.standings] == [True, True, False]


def test_top_cut_falls_back_to_a_consistent_standing_order(tmp_path) -> None:
    snapshot = read(tmp_path, open_event())

    assert snapshot.top_cut_basis["synthetic-open"] == STANDING_ORDER
    assert [s.made_top_cut for s in snapshot.standings] == [True, True, False, False]


def test_an_order_contradicted_by_records_leaves_top_cut_unknown(tmp_path) -> None:
    snapshot = read(tmp_path, event("synthetic-shuffled", [row(1), row(3), row(0)], top_cut=1))

    assert snapshot.top_cut_basis["synthetic-shuffled"] == INCONSISTENT_ORDER
    assert [s.made_top_cut for s in snapshot.standings] == [None, None, None]


def test_missing_records_leave_top_cut_unknown(tmp_path) -> None:
    rows = [row(1), {**row(0), "wins": None}]
    snapshot = read(tmp_path, event("synthetic-unrecorded", rows, top_cut=1))

    assert snapshot.top_cut_basis["synthetic-unrecorded"] == INCONSISTENT_ORDER
    assert snapshot.tournaments[0].coverage.standings.scope is CoverageScope.PARTIAL


def test_a_cut_as_large_as_the_field_puts_everyone_in_it(tmp_path) -> None:
    snapshot = read(tmp_path, event("synthetic-bracket-only", [row(1), row(0)], top_cut=8))

    assert [s.made_top_cut for s in snapshot.standings] == [True, True]


def test_events_without_a_top_cut_record_no_cut_result(tmp_path) -> None:
    snapshot = read(tmp_path, weekly_event())

    assert snapshot.top_cut_basis["synthetic-weekly"] == NO_TOP_CUT
    assert [s.made_top_cut for s in snapshot.standings] == [None, None]


def test_facts_carry_provenance_back_to_the_raw_file(tmp_path) -> None:
    snapshot = read(
        tmp_path, open_event(), retrieved_at={"search.json": "2026-10-18T05:40:00+00:00"}
    )
    provenance = snapshot.decks[0].provenance

    assert provenance.source == "topdeck"
    assert provenance.source_record_id == "synthetic-open#1"
    assert provenance.parser_version == PARSER_VERSION
    assert provenance.raw_snapshot_ref == "saved/search.json"
    assert provenance.retrieved_at == datetime(2026, 10, 18, 5, 40, tzinfo=UTC)
    assert snapshot.raw_files[0].retrieved_at_basis == "manifest"


def test_without_a_manifest_timestamp_the_file_write_time_is_used(tmp_path) -> None:
    snapshot = read(tmp_path, open_event())

    assert snapshot.raw_files[0].retrieved_at_basis == "file_mtime"
    assert snapshot.raw_files[0].retrieved_at.tzinfo is UTC


def test_a_file_that_does_not_match_its_manifest_hash_is_rejected(tmp_path) -> None:
    directory = save(tmp_path / "saved", {"search.json": [open_event()]})
    (directory / "search.json").write_text(json.dumps([weekly_event()]))

    with pytest.raises(ValueError, match="does not match its manifest SHA-256"):
        read_saved_responses(directory)


def test_an_event_repeated_across_files_is_read_once(tmp_path) -> None:
    directory = save(
        tmp_path / "saved", {"a.json": [open_event()], "b.json": [open_event(), weekly_event()]}
    )
    snapshot = read_saved_responses(directory)

    assert [t.source_event_id for t in snapshot.tournaments] == [
        "synthetic-open",
        "synthetic-weekly",
    ]


def test_an_event_repeated_with_different_content_is_rejected(tmp_path) -> None:
    changed = {**open_event(), "topCut": 4}
    directory = save(tmp_path / "saved", {"a.json": [open_event()], "b.json": [changed]})

    with pytest.raises(ValueError, match="appears twice with different content"):
        read_saved_responses(directory)


def test_the_dataset_identity_depends_only_on_the_verified_bytes(tmp_path) -> None:
    first = read_saved_responses(save(tmp_path / "one", {"search.json": [open_event()]}))
    again = read_saved_responses(save(tmp_path / "two", {"search.json": [open_event()]}))
    other = read_saved_responses(save(tmp_path / "three", {"search.json": [weekly_event()]}))

    assert first.dataset_snapshot_id == again.dataset_snapshot_id
    assert first.dataset_snapshot_id != other.dataset_snapshot_id
    assert first.dataset_snapshot_id.startswith("topdeck-")
