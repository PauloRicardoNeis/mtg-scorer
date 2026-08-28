from datetime import UTC, datetime

import pytest

from mtg_scorer import (
    CoverageDimension,
    CoverageProfile,
    CoverageScope,
    DeckCard,
    DeckEntry,
    Match,
    MatchParticipant,
    MatchResult,
    Provenance,
    Standing,
)


def provenance(record_id: str = "record-1") -> Provenance:
    return Provenance(
        source="fixture",
        source_record_id=record_id,
        retrieved_at=datetime(2026, 8, 28, tzinfo=UTC),
        parser_version="fixture-v1",
        raw_snapshot_ref="fixtures/source.json",
    )


def test_provenance_requires_a_timezone_aware_retrieval_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Provenance(
            source="fixture",
            source_record_id="event-1",
            retrieved_at=datetime(2026, 8, 28),
            parser_version="fixture-v1",
            raw_snapshot_ref="fixtures/source.json",
        )


def test_coverage_dimensions_remain_independent() -> None:
    coverage = CoverageProfile(
        decklists=CoverageDimension(CoverageScope.PARTIAL, 75, 100),
        standings=CoverageDimension(CoverageScope.FULL_FIELD, 100, 100),
        matches=CoverageDimension(CoverageScope.NONE, 0, 90),
    )

    assert coverage.decklists.observed_fraction == 0.75
    assert coverage.standings.observed_fraction == 1.0
    assert coverage.matches.observed_fraction == 0.0


def test_coverage_rejects_impossible_counts() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        CoverageDimension(CoverageScope.PARTIAL, observed_count=11, expected_count=10)


def test_deck_entry_rejects_duplicate_oracle_ids() -> None:
    card = DeckCard("oracle-1", "Example", mainboard_count=4)

    with pytest.raises(ValueError, match="oracle_id"):
        DeckEntry(
            provenance=provenance("deck-1"),
            source_event_id="event-1",
            cards=(card, card),
        )


def test_standing_keeps_source_aggregate_separate_from_deck() -> None:
    standing = Standing(
        provenance=provenance("standing-1"),
        source_event_id="event-1",
        source_deck_id="deck-1",
        final_rank=3,
        wins=5,
        losses=2,
        draws=1,
        byes=1,
    )

    assert standing.recorded_matches == 8


def test_match_supports_round_level_results() -> None:
    match = Match(
        provenance=provenance("match-1"),
        source_event_id="event-1",
        round_number=2,
        table_number=4,
        participants=(
            MatchParticipant("deck-1", MatchResult.WIN, games_won=2),
            MatchParticipant("deck-2", MatchResult.LOSS, games_won=1),
        ),
    )

    assert match.participants[0].result is MatchResult.WIN


def test_match_rejects_duplicate_participants() -> None:
    participant = MatchParticipant("deck-1", MatchResult.UNKNOWN)

    with pytest.raises(ValueError, match="unique"):
        Match(
            provenance=provenance("match-1"),
            source_event_id="event-1",
            participants=(participant, participant),
        )
