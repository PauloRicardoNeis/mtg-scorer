from datetime import UTC, date, datetime

import pytest

from mtg_scorer import (
    CardPrinting,
    CoverageDimension,
    CoverageProfile,
    CoverageScope,
    DeckCard,
    DeckEntry,
    Match,
    MatchParticipant,
    MatchResult,
    OracleCard,
    Provenance,
    Standing,
    Tournament,
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


RETRIEVED = datetime(2026, 8, 28, tzinfo=UTC)


@pytest.mark.parametrize(
    ("build", "message"),
    [
        pytest.param(
            lambda: CoverageDimension(CoverageScope.PARTIAL, observed_count=-1),
            "observed_count cannot be negative",
            id="coverage-negative-observed",
        ),
        pytest.param(
            lambda: CoverageDimension(CoverageScope.PARTIAL, expected_count=-1),
            "expected_count cannot be negative",
            id="coverage-negative-expected",
        ),
        pytest.param(
            lambda: CoverageDimension(CoverageScope.NONE, observed_count=3, expected_count=10),
            "NONE coverage",
            id="none-coverage-with-records",
        ),
        pytest.param(
            lambda: Provenance(" ", "record-1", RETRIEVED, "fixture-v1", "fixtures/source.json"),
            "source cannot be blank",
            id="provenance-blank-source",
        ),
        pytest.param(
            lambda: Provenance("fixture", "record-1", RETRIEVED, "fixture-v1", ""),
            "raw_snapshot_ref cannot be blank",
            id="provenance-blank-snapshot-ref",
        ),
        pytest.param(lambda: OracleCard(" ", "Example"), "cannot be blank", id="oracle-blank-id"),
        pytest.param(lambda: OracleCard("oracle-1", ""), "cannot be blank", id="oracle-blank-name"),
        pytest.param(
            lambda: CardPrinting("printing-1", "oracle-1", "set", "1", " "),
            "rarity cannot be blank",
            id="printing-blank-rarity",
        ),
        pytest.param(
            lambda: CardPrinting("printing-1", "oracle-1", "", "1", "common"),
            "set_code cannot be blank",
            id="printing-blank-set",
        ),
        pytest.param(
            lambda: Tournament(provenance(), date(2026, 8, 1), " ", CoverageProfile()),
            "format_name cannot be blank",
            id="tournament-blank-format",
        ),
        pytest.param(
            lambda: Tournament(provenance(), date(2026, 8, 1), "modern", CoverageProfile(), 0),
            "player_count must be positive",
            id="tournament-empty-field",
        ),
        pytest.param(
            lambda: Tournament(
                provenance(),
                date(2026, 8, 2),
                "modern",
                CoverageProfile(),
                ended_on=date(2026, 8, 1),
            ),
            "ended_on cannot precede occurred_on",
            id="tournament-ends-before-start",
        ),
        pytest.param(lambda: DeckCard(" ", "Example", 1), "cannot be blank", id="deck-card-blank"),
        pytest.param(
            lambda: DeckCard("oracle-1", "Example", mainboard_count=-1, sideboard_count=2),
            "cannot be negative",
            id="deck-card-negative",
        ),
        pytest.param(
            lambda: DeckCard("oracle-1", "Example"), "at least one copy", id="deck-card-empty"
        ),
        pytest.param(
            lambda: DeckEntry(provenance("deck-1"), " ", ()),
            "source_event_id cannot be blank",
            id="deck-blank-event",
        ),
        pytest.param(
            lambda: Standing(provenance(), "event-1", " "),
            "identifiers cannot be blank",
            id="standing-blank-deck",
        ),
        pytest.param(
            lambda: Standing(provenance(), "event-1", "deck-1", final_rank=0),
            "final_rank must be positive",
            id="standing-rank-zero",
        ),
        pytest.param(
            lambda: Standing(provenance(), "event-1", "deck-1", byes=-1),
            "byes cannot be negative",
            id="standing-negative-byes",
        ),
        pytest.param(
            lambda: MatchParticipant(" ", MatchResult.WIN),
            "source_deck_id cannot be blank",
            id="participant-blank-deck",
        ),
        pytest.param(
            lambda: MatchParticipant("deck-1", MatchResult.WIN, games_won=-1),
            "games_won cannot be negative",
            id="participant-negative-games",
        ),
        pytest.param(
            lambda: Match(provenance(), " ", (MatchParticipant("deck-1", MatchResult.BYE),)),
            "source_event_id cannot be blank",
            id="match-blank-event",
        ),
        pytest.param(
            lambda: Match(provenance(), "event-1", ()),
            "at least one participant",
            id="match-without-participants",
        ),
        pytest.param(
            lambda: Match(
                provenance(),
                "event-1",
                (MatchParticipant("deck-1", MatchResult.BYE),),
                table_number=0,
            ),
            "table_number must be positive",
            id="match-table-zero",
        ),
    ],
)
def test_source_facts_reject_impossible_values(build, message) -> None:
    with pytest.raises(ValueError, match=message):
        build()


def test_unknown_or_empty_denominators_do_not_become_a_measured_fraction() -> None:
    assert CoverageDimension(CoverageScope.PARTIAL, observed_count=3).observed_fraction is None
    assert CoverageDimension(CoverageScope.NONE, 0, 0).observed_fraction is None
    assert CoverageDimension.unknown().observed_fraction is None
    default = CoverageProfile()
    assert {default.decklists.scope, default.standings.scope, default.matches.scope} == {
        CoverageScope.UNKNOWN
    }


def test_byes_alone_are_not_recorded_matches() -> None:
    only_byes = Standing(provenance(), "event-1", "deck-1", byes=2)
    partial = Standing(provenance(), "event-1", "deck-1", wins=3, byes=1)

    assert only_byes.recorded_matches is None
    assert partial.recorded_matches == 3


def test_source_identifiers_are_derived_from_provenance() -> None:
    tournament = Tournament(
        provenance("event-9"),
        date(2026, 8, 1),
        "modern",
        CoverageProfile(),
        player_count=64,
        ended_on=date(2026, 8, 1),
    )
    deck = DeckEntry(
        provenance("deck-9"),
        source_event_id=tournament.source_event_id,
        cards=(
            DeckCard("oracle-1", "Example", mainboard_count=4),
            DeckCard("oracle-2", "Sideboard Example", sideboard_count=2),
        ),
    )

    assert tournament.source_event_id == "event-9"
    assert deck.source_deck_id == "deck-9"
    assert [card.total_count for card in deck.cards] == [4, 2]


def test_catalog_identities_keep_unknown_release_dates_unknown() -> None:
    card = OracleCard("oracle-1", "Example")
    undated = CardPrinting("printing-1", card.oracle_id, "set", "1", "common")
    dated = CardPrinting("printing-2", card.oracle_id, "set", "2", "rare", date(2026, 8, 1))

    assert undated.released_on is None
    assert dated.released_on == date(2026, 8, 1)
