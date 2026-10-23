"""Valid-side boundaries and pinned formula constants (SYNTHETIC data).

Every test here answers a surviving mutant of the 2026-10-18 mutation pilot
(docs/qa/mutation-testing.md): the suite rejected the invalid side of each threshold
but never asserted the last accepted value, and it bounded the Evidence constants
without stating what they mean. A changed comparison or constant now fails a test
that names the behaviour it protects.
"""

from datetime import UTC, date, datetime
from math import exp

import pytest
from synthetic_topdeck import BOLT, ISLAND, deck, event, row, save

from mtg_scorer import (
    CardFeatures,
    DeckCard,
    FeatureObservation,
    Match,
    MatchParticipant,
    MatchResult,
    Provenance,
    ScoreConfig,
    ScoreContext,
    Standing,
    Tournament,
    score_card,
)
from mtg_scorer.domain import CoverageProfile
from mtg_scorer.ingest.topdeck import (
    NO_TOP_CUT,
    STANDING_ORDER,
    read_saved_responses,
)
from mtg_scorer.tournament_features import CohortRules, card_usage, select_cohort

CONTEXT = ScoreContext(
    dataset_snapshot_id="fixture-2026-10-21",
    feature_pipeline_version="test-features-v1",
)
RULES = CohortRules(
    version="synthetic-boundaries-v1",
    format_name="Modern",
    starts_on="2026-03-01",
    ends_before="2026-09-01",
)
# Half of the field's lists are published: exactly the default minimum coverage.
HALF_LISTED = [row(1, deck_obj=deck({"Bolt": (BOLT, 4)}))] * 2 + [row(0)] * 2


def observed(value: float) -> FeatureObservation:
    return FeatureObservation.known(value, support=1)


def cohort_of(tmp_path, *events, rules=RULES):
    snapshot = read_saved_responses(save(tmp_path / "saved", {"search.json": list(events)}))
    return select_cohort(
        snapshot.tournaments,
        snapshot.decks,
        snapshot.standings,
        rules,
        incomplete_decks=snapshot.incomplete_mainboards,
    )


def usage_by_id(cohort):
    return {usage.oracle_id: usage for usage in card_usage(cohort)}


def read(tmp_path, *events):
    return read_saved_responses(save(tmp_path / "saved", {"search.json": list(events)}))


# --- Evidence: each saturation scale is the count that earns 1 - 1/e of its weight ---


@pytest.mark.parametrize(
    ("population", "scale", "weight"),
    [
        ("deck_count", 8, "evidence_decks"),
        ("event_count", 4, "evidence_events"),
        ("full_field_match_count", 40, "evidence_matches"),
    ],
)
def test_a_population_at_its_scale_earns_63_percent_of_its_evidence_weight(
    population, scale, weight
) -> None:
    evidence = score_card(CardFeatures(**{population: scale}), CONTEXT).evidence

    assert evidence == pytest.approx(100 * getattr(ScoreConfig(), weight) * (1 - exp(-1)), abs=0.05)


def test_one_fully_observed_model_is_half_the_feature_availability_evidence() -> None:
    # Every staple feature is known, no deck means no build-around model: availability
    # averages the two models, so the term is worth half its weight, 5 points.
    features = CardFeatures(
        incidence=observed(0.5),
        deck_family_breadth=observed(0.5),
        format_era_breadth=observed(0.5),
        competitive_proof=observed(0.5),
        commitment=observed(0.5),
    )

    scores = score_card(features, CONTEXT)

    assert scores.staple_feature_coverage == 100.0
    assert scores.buildaround_feature_coverage == 0.0
    assert scores.evidence == 100 * ScoreConfig().evidence_feature_availability / 2


def test_feature_coverage_keeps_one_decimal() -> None:
    # The default weights are multiples of 5%, so a coverage is only fractional under a
    # configuration whose single known feature carries a weight such as 37.5%.
    config = ScoreConfig(
        version="boundary-test",
        staple_incidence=0.375,
        staple_deck_family_breadth=0.225,
        buildaround_specificity=0.275,
        buildaround_package_coherence=0.225,
    )
    features = CardFeatures(incidence=observed(0.5), specificity=observed(0.5), deck_count=1)

    scores = score_card(features, CONTEXT, config)

    assert scores.staple_feature_coverage == 37.5
    assert scores.buildaround_feature_coverage == 27.5


def test_a_feature_with_no_opportunity_and_no_support_is_a_valid_observation() -> None:
    observation = FeatureObservation.known(0.0, support=0, opportunity_count=0)

    assert (observation.support, observation.opportunity_count) == (0, 0)
    assert observation.is_known


# --- Cohort rules: the window includes its first day and excludes its end ---


def test_full_decklist_coverage_is_an_accepted_minimum() -> None:
    rules = CohortRules(
        version="synthetic-strict-v1",
        format_name="Modern",
        starts_on="2026-03-01",
        ends_before="2026-09-01",
        min_decklist_coverage=1.0,
    )

    assert rules.min_decklist_coverage == 1.0


def test_an_event_on_the_first_day_is_in_the_window_and_one_on_the_end_date_is_not(
    tmp_path,
) -> None:
    listed = deck({"Bolt": (BOLT, 4)})
    cohort = cohort_of(
        tmp_path,
        event("synthetic-first-day", [row(1, deck_obj=listed)], day="2026-03-01"),
        event("synthetic-day-before", [row(1, deck_obj=listed)], day="2026-02-28"),
        event("synthetic-last-day", [row(1, deck_obj=listed)], day="2026-08-31"),
        event("synthetic-end-date", [row(1, deck_obj=listed)], day="2026-09-01"),
    )

    assert [t.source_event_id for t in cohort.tournaments] == [
        "synthetic-first-day",
        "synthetic-last-day",
    ]
    assert {e.source_event_id: e.reason for e in cohort.excluded_events} == {
        "synthetic-day-before": "outside the cohort window",
        "synthetic-end-date": "outside the cohort window",
    }


def test_decklist_coverage_equal_to_the_minimum_is_enough(tmp_path) -> None:
    cohort = cohort_of(tmp_path, event("synthetic-half", HALF_LISTED))

    assert [t.source_event_id for t in cohort.tournaments] == ["synthetic-half"]
    assert cohort.excluded_events == ()
    assert cohort.tournaments[0].coverage.decklists.observed_fraction == RULES.min_decklist_coverage


# --- Card usage: a single copy counts, the majority spelling names a card ---


def test_a_single_mainboard_copy_counts_the_card(tmp_path) -> None:
    one_of = deck({"Bolt": (BOLT, 1)})
    usage = usage_by_id(cohort_of(tmp_path, event("synthetic-one-of", [row(1, deck_obj=one_of)])))

    bolt = usage[BOLT]
    assert (bolt.deck_count, bolt.mainboard_copies, bolt.playset_deck_count) == (1, 1, 0)
    assert (bolt.decks, bolt.deck_copies) == ((0,), (1,))


def test_the_majority_spelling_names_a_card_over_the_alphabetically_first(tmp_path) -> None:
    rows = [
        row(2, deck_obj=deck({"Snow Island": (ISLAND, 10)})),
        row(1, deck_obj=deck({"Snow Island": (ISLAND, 10)})),
        row(0, deck_obj=deck({"Island": (ISLAND, 10)})),
    ]
    usage = usage_by_id(cohort_of(tmp_path, event("synthetic-spellings", rows)))

    assert usage[ISLAND].name == "Snow Island"


def test_a_card_seen_only_in_unlabelled_decks_has_zero_archetype_decks(tmp_path) -> None:
    usage = usage_by_id(
        cohort_of(tmp_path, event("synthetic-plain", [row(1, deck_obj=deck({"Bolt": (BOLT, 4)}))]))
    )

    bolt = usage[BOLT]
    assert (bolt.archetype_label, bolt.archetype_deck_count) == (None, 0)
    assert (bolt.archetypes, bolt.archetype_count, bolt.labelled_deck_count) == ((), 0, 0)


# --- TopDeck top cut: ties at the boundary and cuts as wide as the field ---


def test_a_null_top_cut_means_no_cut(tmp_path) -> None:
    snapshot = read(tmp_path, {**event("synthetic-null-cut", [row(1)]), "topCut": None})

    assert snapshot.tournaments[0].top_cut_size == 0
    assert snapshot.top_cut_basis["synthetic-null-cut"] == NO_TOP_CUT


def test_bracket_wins_without_bracket_losses_are_not_a_bracket_record(tmp_path) -> None:
    rows = [row(2, winsBracket=1), row(1, winsBracket=0)]
    snapshot = read(tmp_path, event("synthetic-half-bracket", rows, top_cut=1))

    assert snapshot.top_cut_basis["synthetic-half-bracket"] == STANDING_ORDER
    assert [s.made_top_cut for s in snapshot.standings] == [True, False]


def test_a_cut_exactly_as_large_as_the_field_puts_everyone_in_it(tmp_path) -> None:
    snapshot = read(tmp_path, event("synthetic-exact-cut", [row(2), row(1)], top_cut=2))

    assert snapshot.top_cut_basis["synthetic-exact-cut"] == STANDING_ORDER
    assert [s.made_top_cut for s in snapshot.standings] == [True, True]


def test_a_wins_tie_across_the_cut_boundary_keeps_the_standing_order(tmp_path) -> None:
    # Nobody below the cut has more wins than somebody inside it, so the source's order
    # stands; tiebreakers decided the cut, and the response order reports them.
    snapshot = read(tmp_path, event("synthetic-tie", [row(3), row(2), row(2)], top_cut=2))

    assert snapshot.top_cut_basis["synthetic-tie"] == STANDING_ORDER
    assert [s.made_top_cut for s in snapshot.standings] == [True, True, False]


# --- Domain facts: the first valid value of every positive or non-negative field ---

PROVENANCE = Provenance(
    source="fixture",
    source_record_id="record-1",
    retrieved_at=datetime(2026, 10, 21, tzinfo=UTC),
    parser_version="fixture-v1",
    raw_snapshot_ref="fixtures/source.json",
)


def test_a_card_with_equal_mainboard_and_sideboard_copies_counts_both() -> None:
    card = DeckCard("oracle-1", "Example", mainboard_count=2, sideboard_count=2)

    assert card.total_count == 4


def test_a_winner_with_no_recorded_games_is_a_valid_standing() -> None:
    standing = Standing(
        PROVENANCE, "event-1", "deck-1", final_rank=1, wins=0, losses=0, draws=0, byes=0
    )

    assert standing.final_rank == 1
    assert standing.recorded_matches == 0


def test_a_participant_who_won_no_games_is_valid() -> None:
    assert MatchParticipant("deck-1", MatchResult.LOSS, games_won=0).games_won == 0


def test_round_one_at_table_one_is_a_valid_match() -> None:
    match = Match(
        PROVENANCE,
        "event-1",
        (MatchParticipant("deck-1", MatchResult.BYE),),
        round_number=1,
        table_number=1,
    )

    assert (match.round_number, match.table_number) == (1, 1)


def test_a_one_player_event_without_a_cut_is_a_valid_tournament() -> None:
    tournament = Tournament(
        PROVENANCE,
        date(2026, 10, 21),
        "Modern",
        CoverageProfile(),
        player_count=1,
        top_cut_size=0,
    )

    assert (tournament.player_count, tournament.top_cut_size) == (1, 0)
