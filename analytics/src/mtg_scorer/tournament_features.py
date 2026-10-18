"""Per-card usage inside one bounded tournament cohort.

A cohort is one source, format and date window, restricted to events whose
decklists cover enough of the field to describe it. Every count keeps its
denominator, and a card is only ever counted from decks whose mainboard was read
completely.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date

from .domain import DeckEntry, Standing, Tournament
from .features import CardFeatures, FeatureObservation
from .scoring.base import config_fingerprint

FEATURE_PIPELINE_VERSION = "card-usage-v1"


@dataclass(frozen=True, slots=True)
class ExcludedEvent:
    source_event_id: str
    reason: str

    def __post_init__(self) -> None:
        if not self.source_event_id.strip() or not self.reason.strip():
            raise ValueError("an excluded event needs an identifier and a reason")


@dataclass(frozen=True, slots=True)
class CohortRules:
    """Which events of one format and window count as field evidence.

    Dates are ISO strings so the rules hash the same way everywhere. The window
    includes ``starts_on`` and excludes ``ends_before``.
    """

    version: str
    format_name: str
    starts_on: str
    ends_before: str
    min_decklist_coverage: float = 0.5
    excluded_events: tuple[ExcludedEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.format_name.strip():
            raise ValueError("version and format_name cannot be blank")
        if date.fromisoformat(self.ends_before) <= date.fromisoformat(self.starts_on):
            raise ValueError("ends_before must be after starts_on")
        if not 0.0 < self.min_decklist_coverage <= 1.0:
            raise ValueError("min_decklist_coverage must be in (0, 1]")
        ids = [event.source_event_id for event in self.excluded_events]
        if len(ids) != len(set(ids)):
            raise ValueError("an event can only be excluded once")

    @property
    def fingerprint(self) -> str:
        return config_fingerprint(self)


@dataclass(frozen=True, slots=True)
class Cohort:
    """The events, decks and standings that passed the rules, and why others did not."""

    rules: CohortRules
    tournaments: tuple[Tournament, ...]
    decks: tuple[DeckEntry, ...]
    standings: tuple[Standing, ...]
    excluded_events: tuple[ExcludedEvent, ...]
    incomplete_deck_count: int


@dataclass(frozen=True, slots=True)
class CardUsage:
    """How often one card appeared in the cohort's mainboards.

    ``top_cut_count`` counts only the card's decks whose top-cut result is known;
    ``top_cut_known_decks`` is that denominator, and the count is ``None`` when it is 0.
    """

    oracle_id: str
    name: str
    deck_count: int
    event_count: int
    top_cut_count: int | None
    top_cut_known_decks: int
    archetype_label: str | None
    archetype_deck_count: int
    labelled_deck_count: int


def select_cohort(
    tournaments: Iterable[Tournament],
    decks: Iterable[DeckEntry],
    standings: Iterable[Standing],
    rules: CohortRules,
    *,
    incomplete_decks: Collection[str] = frozenset(),
) -> Cohort:
    rule_exclusions = {event.source_event_id: event.reason for event in rules.excluded_events}
    starts_on = date.fromisoformat(rules.starts_on)
    ends_before = date.fromisoformat(rules.ends_before)
    included: list[Tournament] = []
    excluded: list[ExcludedEvent] = []
    for tournament in sorted(tournaments, key=lambda event: event.source_event_id):
        reason = _exclusion_reason(tournament, rules, rule_exclusions, starts_on, ends_before)
        if reason is None:
            included.append(tournament)
        else:
            excluded.append(ExcludedEvent(tournament.source_event_id, reason))
    event_ids = {tournament.source_event_id for tournament in included}
    cohort_decks = [deck for deck in decks if deck.source_event_id in event_ids]
    complete = tuple(deck for deck in cohort_decks if deck.source_deck_id not in incomplete_decks)
    return Cohort(
        rules=rules,
        tournaments=tuple(included),
        decks=complete,
        standings=tuple(s for s in standings if s.source_event_id in event_ids),
        excluded_events=tuple(excluded),
        incomplete_deck_count=len(cohort_decks) - len(complete),
    )


def _exclusion_reason(
    tournament: Tournament,
    rules: CohortRules,
    rule_exclusions: dict[str, str],
    starts_on: date,
    ends_before: date,
) -> str | None:
    if tournament.source_event_id in rule_exclusions:
        return f"excluded by rule: {rule_exclusions[tournament.source_event_id]}"
    if tournament.format_name != rules.format_name:
        return f"format {tournament.format_name!r} is not {rules.format_name!r}"
    if not starts_on <= tournament.occurred_on < ends_before:
        return "outside the cohort window"
    coverage = tournament.coverage.decklists.observed_fraction
    if coverage is None:
        return "decklist coverage unknown"
    if coverage < rules.min_decklist_coverage:
        return f"decklist coverage {coverage:.0%} is below {rules.min_decklist_coverage:.0%}"
    return None


def card_usage(cohort: Cohort) -> tuple[CardUsage, ...]:
    """Count each mainboard card's decks, events, top cuts and most common label."""

    made_cut = {standing.source_deck_id: standing.made_top_cut for standing in cohort.standings}
    decks_by_card: dict[str, list[DeckEntry]] = {}
    names: dict[str, Counter[str]] = {}
    for deck in cohort.decks:
        for card in deck.cards:
            if card.mainboard_count > 0:
                decks_by_card.setdefault(card.oracle_id, []).append(deck)
                names.setdefault(card.oracle_id, Counter())[card.name] += 1

    usage = []
    for oracle_id in sorted(decks_by_card):
        card_decks = decks_by_card[oracle_id]
        cut_results = [made_cut.get(deck.source_deck_id) for deck in card_decks]
        known = [result for result in cut_results if result is not None]
        labels = Counter(deck.archetype_label for deck in card_decks if deck.archetype_label)
        label, label_decks = _most_common(labels)
        usage.append(
            CardUsage(
                oracle_id=oracle_id,
                name=_most_common(names[oracle_id])[0],
                deck_count=len(card_decks),
                event_count=len({deck.source_event_id for deck in card_decks}),
                top_cut_count=sum(known) if known else None,
                top_cut_known_decks=len(known),
                archetype_label=label,
                archetype_deck_count=label_decks,
                labelled_deck_count=sum(labels.values()),
            )
        )
    return tuple(usage)


def _most_common(counts: Counter[str]) -> tuple[str | None, int]:
    # Ties go to the alphabetically first value so reruns are identical.
    if not counts:
        return None, 0
    value, count = min(counts.items(), key=lambda item: (-item[1], item[0]))
    return value, count


def card_features(usage: CardUsage, cohort: Cohort) -> CardFeatures:
    """Express one card's usage as the missing-aware features score methods consume."""

    decks = len(cohort.decks)
    return CardFeatures(
        incidence=FeatureObservation.known(
            usage.deck_count / decks, support=usage.deck_count, opportunity_count=decks
        ),
        deck_count=usage.deck_count,
        event_count=usage.event_count,
    )
