"""Per-card usage inside one bounded tournament cohort.

A cohort is one source, format and date window, restricted to events whose
decklists cover enough of the field to describe it. Every count keeps its
denominator, and a card is only ever counted from decks whose mainboard was read
completely.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from .domain import DeckEntry, Standing, Tournament
from .features import CardFeatures, FeatureObservation
from .scoring.base import config_fingerprint

FEATURE_PIPELINE_VERSION = "card-usage-v4"
# The trend series: twelve periods ending where the cohort window ends, each a
# twelfth of the window but at most 30 days. Weeks would leave most periods empty in
# formats with a few events a month.
SERIES_PERIODS = 12
SERIES_PERIOD_DAYS = 30
# A card names at most this many archetypes; the rest are only counted.
TOP_ARCHETYPES = 3
# A card belongs to an archetype's core when at least this share of its decks play it.
CORE_CARD_SHARE = 0.5
# Joins partner commanders into the name of their one archetype.
COMMANDER_SEPARATOR = " + "
# Published fractions are rounded so reruns write identical files.
DIGITS = 4


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
    # 2 for one-on-one matches; multiplayer formats such as EDH play pods of 4.
    players_per_game: int = 2

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.format_name.strip():
            raise ValueError("version and format_name cannot be blank")
        if self.players_per_game < 2:
            raise ValueError("players_per_game must be at least 2")
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
class Record:
    """Summed match results of the decks whose standing reported wins, losses and draws.

    Byes are not matches, so they never count.
    """

    decks: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0

    @property
    def games(self) -> int:
        return self.wins + self.losses + self.draws

    def win_rate(self, players_per_game: int) -> float | None:
        """Match points per game: a draw shares the win among the players at the table,
        so a one-on-one field averages 50% and a four-player pod field 25%."""

        if not self.games:
            return None
        return (self.wins + self.draws / players_per_game) / self.games


def _record(standings: Iterable[Standing]) -> Record:
    known = [
        s for s in standings if s.wins is not None and s.losses is not None and s.draws is not None
    ]
    return Record(
        decks=len(known),
        wins=sum(s.wins or 0 for s in known),
        losses=sum(s.losses or 0 for s in known),
        draws=sum(s.draws or 0 for s in known),
    )


@dataclass(frozen=True, slots=True)
class CardUsage:
    """How often one card appeared in the cohort's mainboards.

    ``top_cut_count`` counts only the card's decks whose top-cut result is known;
    ``top_cut_known_decks`` is that denominator, and the count is ``None`` when it is 0.
    ``archetypes`` names the most common archetypes (see ``deck_archetypes``) with their
    decks, ``series`` the card's decks in each trend period, and ``record`` the match
    results of its decks. ``archetype_concentration`` is the chance that two of its
    labelled decks share an archetype, unknown below two labelled decks.
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
    mainboard_copies: int = 0
    record: Record = Record()
    archetypes: tuple[tuple[str, int], ...] = ()
    archetype_count: int = 0
    series: tuple[int, ...] = ()
    archetype_concentration: float | None = None


@dataclass(frozen=True, slots=True)
class ArchetypeCore:
    """One archetype label, its decks and the cards most of them play."""

    label: str
    deck_count: int
    core_cards: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CohortPerformance:
    """The field baselines every card is compared with, and the trend denominators."""

    players_per_game: int
    record: Record
    top_cut_known_decks: int
    top_cut_decks: int
    series_period_days: int
    series_starts_on: date
    series: tuple[int, ...]
    archetypes: tuple[ArchetypeCore, ...]
    # The chance that two labelled decks of the field share an archetype.
    archetype_concentration: float | None = None

    @property
    def win_rate(self) -> float | None:
        return self.record.win_rate(self.players_per_game)

    @property
    def top_cut_rate(self) -> float | None:
        return self.top_cut_decks / self.top_cut_known_decks if self.top_cut_known_decks else None

    @property
    def matches(self) -> int:
        # Every player at a table reports the same game, so games divide by the table size.
        return self.record.games // self.players_per_game


@dataclass(frozen=True, slots=True)
class CardPerformance:
    """How one card's decks did against the field. ``None`` means unknown, never zero."""

    win_rate: float | None
    win_rate_delta: float | None
    win_rate_ci95: float | None
    top_cut_lift: float | None
    share_delta: float | None


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


def series_period_days(rules: CohortRules) -> int:
    """A twelfth of the window, rounded up, and at most ``SERIES_PERIOD_DAYS``."""

    window = (date.fromisoformat(rules.ends_before) - date.fromisoformat(rules.starts_on)).days
    return min(SERIES_PERIOD_DAYS, -(-window // SERIES_PERIODS))


def _series_index(occurred_on: date, rules: CohortRules) -> int | None:
    """The trend period an event falls in, counted from the oldest; ``None`` before it."""

    periods_back = ((date.fromisoformat(rules.ends_before) - occurred_on).days - 1) // (
        series_period_days(rules)
    )
    index = SERIES_PERIODS - 1 - periods_back
    return index if 0 <= index < SERIES_PERIODS else None


def _series(decks: Iterable[DeckEntry], periods: dict[str, int | None]) -> tuple[int, ...]:
    counts = [0] * SERIES_PERIODS
    for deck in decks:
        index = periods[deck.source_event_id]
        if index is not None:
            counts[index] += 1
    return tuple(counts)


def deck_archetypes(cohort: Cohort) -> dict[str, str]:
    """Each labelled deck's archetype by deck id: the source's label, or its commanders.

    TopDeck labels only 60-card formats, so an unlabelled commander deck belongs to
    the archetype of its commanders, a partner pair being one archetype. Commanders
    are named as the cohort's decks most often spell them, so a card listed under two
    names (a double-faced card with or without its back face) stays one archetype.
    """

    commander_ids = {
        oracle_id
        for deck in cohort.decks
        if not deck.archetype_label
        for oracle_id in deck.commanders
    }
    spellings: dict[str, Counter[str]] = {}
    if commander_ids:
        for deck in cohort.decks:
            for card in deck.cards:
                if card.oracle_id in commander_ids and card.mainboard_count > 0:
                    spellings.setdefault(card.oracle_id, Counter())[card.name] += 1
    names = {oracle_id: _most_common(counts)[0] for oracle_id, counts in spellings.items()}
    archetypes = {}
    for deck in cohort.decks:
        if deck.archetype_label:
            archetypes[deck.source_deck_id] = deck.archetype_label
        elif deck.commanders:
            archetypes[deck.source_deck_id] = COMMANDER_SEPARATOR.join(
                sorted(names[oracle_id] for oracle_id in deck.commanders)
            )
    return archetypes


def card_usage(cohort: Cohort) -> tuple[CardUsage, ...]:
    """Count each mainboard card's decks, events, top cuts, archetypes, copies, record and trend."""

    archetype_of = deck_archetypes(cohort)
    made_cut = {standing.source_deck_id: standing.made_top_cut for standing in cohort.standings}
    standing_of = {standing.source_deck_id: standing for standing in cohort.standings}
    periods = {
        t.source_event_id: _series_index(t.occurred_on, cohort.rules) for t in cohort.tournaments
    }
    decks_by_card: dict[str, list[DeckEntry]] = {}
    names: dict[str, Counter[str]] = {}
    copies: Counter[str] = Counter()
    for deck in cohort.decks:
        for card in deck.cards:
            if card.mainboard_count > 0:
                decks_by_card.setdefault(card.oracle_id, []).append(deck)
                names.setdefault(card.oracle_id, Counter())[card.name] += 1
                copies[card.oracle_id] += card.mainboard_count

    usage = []
    for oracle_id in sorted(decks_by_card):
        card_decks = decks_by_card[oracle_id]
        cut_results = [made_cut.get(deck.source_deck_id) for deck in card_decks]
        known = [result for result in cut_results if result is not None]
        labels = Counter(
            archetype_of[deck.source_deck_id]
            for deck in card_decks
            if deck.source_deck_id in archetype_of
        )
        ranked = _ranked(labels)
        label, label_decks = ranked[0] if ranked else (None, 0)
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
                mainboard_copies=copies[oracle_id],
                record=_record(
                    standing_of[deck.source_deck_id]
                    for deck in card_decks
                    if deck.source_deck_id in standing_of
                ),
                archetypes=tuple(ranked[:TOP_ARCHETYPES]),
                archetype_count=len(ranked),
                series=_series(card_decks, periods),
                archetype_concentration=_concentration(labels.values()),
            )
        )
    return tuple(usage)


def _concentration(counts: Iterable[int]) -> float | None:
    """The chance that two different decks drawn from these groups share one: Simpson's
    index without its small-sample bias, so two decks of one label are not certainty."""

    counts = list(counts)
    total = sum(counts)
    if total < 2:
        return None
    return sum(n * (n - 1) for n in counts) / (total * (total - 1))


def _ranked(counts: Counter[str]) -> list[tuple[str, int]]:
    # Ties go to the alphabetically first value so reruns are identical.
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _most_common(counts: Counter[str]) -> tuple[str | None, int]:
    ranked = _ranked(counts)
    return ranked[0] if ranked else (None, 0)


def cohort_performance(cohort: Cohort) -> CohortPerformance:
    """The field's record, top-cut rate, trend denominators and archetype cores."""

    standing_of = {standing.source_deck_id: standing for standing in cohort.standings}
    cut = [
        standing_of[d.source_deck_id].made_top_cut
        for d in cohort.decks
        if d.source_deck_id in standing_of
    ]
    periods = {
        t.source_event_id: _series_index(t.occurred_on, cohort.rules) for t in cohort.tournaments
    }
    archetype_of = deck_archetypes(cohort)
    by_label: dict[str, list[DeckEntry]] = {}
    for deck in cohort.decks:
        if deck.source_deck_id in archetype_of:
            by_label.setdefault(archetype_of[deck.source_deck_id], []).append(deck)
    archetypes = []
    for label in sorted(by_label):
        decks = by_label[label]
        played = Counter(
            card.oracle_id for deck in decks for card in deck.cards if card.mainboard_count > 0
        )
        core = sorted(
            oracle for oracle, count in played.items() if count >= CORE_CARD_SHARE * len(decks)
        )
        archetypes.append(ArchetypeCore(label, len(decks), tuple(core)))
    return CohortPerformance(
        players_per_game=cohort.rules.players_per_game,
        record=_record(
            standing_of[d.source_deck_id] for d in cohort.decks if d.source_deck_id in standing_of
        ),
        top_cut_known_decks=sum(result is not None for result in cut),
        top_cut_decks=sum(result is True for result in cut),
        series_period_days=series_period_days(cohort.rules),
        series_starts_on=date.fromisoformat(cohort.rules.ends_before)
        - timedelta(days=SERIES_PERIODS * series_period_days(cohort.rules)),
        series=_series(cohort.decks, periods),
        archetypes=tuple(archetypes),
        archetype_concentration=_concentration(len(decks) for decks in by_label.values()),
    )


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, DIGITS)


def card_performance(usage: CardUsage, field: CohortPerformance) -> CardPerformance:
    """Compare one card's decks with the field: win rate, top-cut lift and trend."""

    win_rate = usage.record.win_rate(field.players_per_game)
    delta = None if win_rate is None or field.win_rate is None else win_rate - field.win_rate
    # The normal approximation of a proportion's 95% interval, as a half-width.
    ci95 = (
        None
        if win_rate is None
        else 1.96 * math.sqrt(max(win_rate * (1 - win_rate), 0.0) / usage.record.games)
    )
    lift = None
    if usage.top_cut_count is not None and field.top_cut_rate:
        lift = usage.top_cut_count / usage.top_cut_known_decks / field.top_cut_rate
    # The trend compares pooled shares of the older and the newer half of the series,
    # so one thin month cannot swing it.
    half = SERIES_PERIODS // 2
    older, newer = sum(field.series[:half]), sum(field.series[half:])
    share_delta = (
        sum(usage.series[half:]) / newer - sum(usage.series[:half]) / older
        if older and newer
        else None
    )
    return CardPerformance(
        win_rate=_rounded(win_rate),
        win_rate_delta=_rounded(delta),
        win_rate_ci95=_rounded(ci95),
        top_cut_lift=_rounded(lift),
        share_delta=_rounded(share_delta),
    )


def card_features(
    usage: CardUsage, cohort: Cohort, field: CohortPerformance | None = None
) -> CardFeatures:
    """Express one card's usage as the missing-aware features score methods consume."""

    decks = len(cohort.decks)
    field = field or cohort_performance(cohort)
    win_rate = usage.record.win_rate(field.players_per_game)
    cut = usage.top_cut_count
    home = next((a.deck_count for a in field.archetypes if a.label == usage.archetype_label), 0)
    return CardFeatures(
        incidence=FeatureObservation.known(
            usage.deck_count / decks, support=usage.deck_count, opportunity_count=decks
        ),
        win_rate=(
            FeatureObservation.unknown()
            if win_rate is None
            else FeatureObservation.known(win_rate, support=usage.record.games)
        ),
        top_cut_rate=(
            FeatureObservation.unknown()
            if cut is None
            else FeatureObservation.known(
                cut / usage.top_cut_known_decks,
                support=usage.top_cut_known_decks,
                opportunity_count=usage.top_cut_known_decks,
            )
        ),
        archetype_concentration=(
            FeatureObservation.unknown()
            if usage.archetype_concentration is None
            else FeatureObservation.known(
                usage.archetype_concentration, support=usage.labelled_deck_count
            )
        ),
        archetype_adoption=(
            FeatureObservation.known(
                usage.archetype_deck_count / home,
                support=usage.archetype_deck_count,
                opportunity_count=home,
            )
            if home
            else FeatureObservation.unknown()
        ),
        field_win_rate=field.win_rate,
        field_top_cut_rate=field.top_cut_rate,
        field_archetype_concentration=field.archetype_concentration,
        deck_count=usage.deck_count,
        event_count=usage.event_count,
    )
