"""Cohort selection and per-card usage keep their denominators (SYNTHETIC data)."""

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

from mtg_scorer.ingest.topdeck import read_saved_responses
from mtg_scorer.tournament_features import (
    CohortRules,
    ExcludedEvent,
    card_features,
    card_usage,
    select_cohort,
)

RULES = CohortRules(
    version="synthetic-cohort-v1",
    format_name="Modern",
    starts_on="2026-03-01",
    ends_before="2026-09-01",
)


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


def test_events_are_excluded_with_a_stated_reason(tmp_path) -> None:
    rules = CohortRules(
        version="synthetic-cohort-v1",
        format_name="Modern",
        starts_on="2026-03-01",
        ends_before="2026-09-01",
        excluded_events=(ExcludedEvent("synthetic-variant", "older card pool"),),
    )
    listed = deck({"Bolt": (BOLT, 4)})
    cohort = cohort_of(
        tmp_path,
        open_event(),
        event("synthetic-variant", [row(1, deck_obj=listed)]),
        event("synthetic-pioneer", [row(1, deck_obj=listed)], fmt="Pioneer"),
        event("synthetic-late", [row(1, deck_obj=listed)], day="2026-09-05"),
        event("synthetic-local", [row(1, deck_obj=listed), row(0), row(0)]),
        event("synthetic-empty", []),
        rules=rules,
    )

    assert [t.source_event_id for t in cohort.tournaments] == ["synthetic-open"]
    assert {e.source_event_id: e.reason for e in cohort.excluded_events} == {
        "synthetic-empty": "decklist coverage unknown",
        "synthetic-late": "outside the cohort window",
        "synthetic-local": "decklist coverage 33% is below 50%",
        "synthetic-pioneer": "format 'Pioneer' is not 'Modern'",
        "synthetic-variant": "excluded by rule: older card pool",
    }


def test_only_decks_and_standings_of_included_events_remain(tmp_path) -> None:
    listed = deck({"Bolt": (BOLT, 4)})
    cohort = cohort_of(
        tmp_path, open_event(), event("synthetic-local", [row(1, deck_obj=listed)] + [row(0)] * 3)
    )

    assert {d.source_event_id for d in cohort.decks} == {"synthetic-open"}
    assert {s.source_event_id for s in cohort.standings} == {"synthetic-open"}


def test_decks_with_an_incomplete_mainboard_are_left_out_and_counted(tmp_path) -> None:
    broken = deck({"Bolt": (BOLT, 4), "Mystery": ("", 1)})
    cohort = cohort_of(
        tmp_path,
        event(
            "synthetic-broken",
            [row(1, deck_obj=broken), row(0, deck_obj=deck({"Bolt": (BOLT, 4)}))],
        ),
    )

    assert cohort.incomplete_deck_count == 1
    assert [d.source_deck_id for d in cohort.decks] == ["synthetic-broken#2"]


def test_card_usage_counts_decks_events_and_known_top_cuts(tmp_path) -> None:
    usage = usage_by_id(cohort_of(tmp_path, open_event(), weekly_event()))

    bolt = usage[BOLT]
    assert (bolt.deck_count, bolt.event_count) == (3, 2)
    # Two Bolt decks played in the top-2 event; both made the cut. The weekly had none.
    assert (bolt.top_cut_count, bolt.top_cut_known_decks) == (2, 2)
    counterspell = usage[COUNTERSPELL]
    assert (counterspell.deck_count, counterspell.top_cut_count) == (3, 1)
    assert counterspell.top_cut_known_decks == 2


def test_top_cut_count_is_unknown_when_no_deck_has_a_known_result(tmp_path) -> None:
    usage = usage_by_id(cohort_of(tmp_path, weekly_event()))

    assert usage[BOLT].top_cut_count is None
    assert usage[BOLT].top_cut_known_decks == 0


def test_sideboard_only_cards_have_no_mainboard_usage(tmp_path) -> None:
    listed = deck({"Bolt": (BOLT, 4)}, {"Counterspell": (COUNTERSPELL, 2)})
    usage = usage_by_id(cohort_of(tmp_path, event("synthetic-side", [row(1, deck_obj=listed)])))

    assert set(usage) == {BOLT}


def test_the_most_common_archetype_label_is_kept_with_its_support(tmp_path) -> None:
    usage = usage_by_id(cohort_of(tmp_path, open_event(), weekly_event()))

    assert (usage[COUNTERSPELL].archetype_label, usage[COUNTERSPELL].archetype_deck_count) == (
        "Control",
        3,
    )
    assert usage[BOLT].archetype_label == "Burn"
    assert (usage[BOLT].archetype_deck_count, usage[BOLT].labelled_deck_count) == (2, 3)


def test_label_and_name_ties_resolve_alphabetically(tmp_path) -> None:
    rows = [
        row(1, deck_obj=deck({"Island": (ISLAND, 10)}), archetype="Tron"),
        row(0, deck_obj=deck({"Snow Island": (ISLAND, 10)}), archetype="Delver"),
    ]
    usage = usage_by_id(cohort_of(tmp_path, event("synthetic-ties", rows)))

    assert (usage[ISLAND].archetype_label, usage[ISLAND].name) == ("Delver", "Island")


def test_unlabelled_decks_leave_the_archetype_unknown(tmp_path) -> None:
    usage = usage_by_id(
        cohort_of(tmp_path, event("synthetic-plain", [row(1, deck_obj=deck({"Bolt": (BOLT, 4)}))]))
    )

    assert usage[BOLT].archetype_label is None
    assert usage[BOLT].labelled_deck_count == 0


def test_card_features_express_incidence_against_all_cohort_decks(tmp_path) -> None:
    cohort = cohort_of(tmp_path, open_event(), weekly_event())
    features = card_features(usage_by_id(cohort)[BOLT], cohort)

    assert features.incidence.value == pytest.approx(3 / 5)
    assert (features.incidence.support, features.incidence.opportunity_count) == (3, 5)
    assert (features.deck_count, features.event_count) == (3, 2)
    assert not features.specificity.is_known


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"version": " "}, "cannot be blank"),
        ({"ends_before": "2026-03-01"}, "ends_before must be after starts_on"),
        ({"min_decklist_coverage": 0.0}, "min_decklist_coverage"),
        ({"min_decklist_coverage": 1.5}, "min_decklist_coverage"),
        (
            {"excluded_events": (ExcludedEvent("a", "x"), ExcludedEvent("a", "y"))},
            "excluded once",
        ),
    ],
)
def test_cohort_rules_reject_unusable_settings(changes, message) -> None:
    settings = {
        "version": "synthetic-cohort-v1",
        "format_name": "Modern",
        "starts_on": "2026-03-01",
        "ends_before": "2026-09-01",
        **changes,
    }

    with pytest.raises(ValueError, match=message):
        CohortRules(**settings)


def test_excluded_events_need_an_id_and_a_reason() -> None:
    with pytest.raises(ValueError, match="identifier and a reason"):
        ExcludedEvent("synthetic-variant", " ")


def test_the_rules_hash_changes_with_any_setting() -> None:
    stricter = CohortRules(
        version="synthetic-cohort-v1",
        format_name="Modern",
        starts_on="2026-03-01",
        ends_before="2026-09-01",
        min_decklist_coverage=0.8,
    )

    assert RULES.fingerprint != stricter.fingerprint
