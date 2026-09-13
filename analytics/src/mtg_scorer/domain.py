"""Source-independent facts for historical MTG evidence.

Adapters translate source payloads into these types. Analytical features and
scores deliberately live in separate modules so unavailable observations cannot
quietly become analytical conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class CoverageScope(StrEnum):
    """Which portion of a source population was observed for one data dimension."""

    FULL_FIELD = "full_field"
    TOP_CUT = "top_cut"
    WINNERS = "winners"
    PARTIAL = "partial"
    NONE = "none"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CoverageDimension:
    """Coverage for decklists, standings, or matches independently."""

    scope: CoverageScope
    observed_count: int | None = None
    expected_count: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("observed_count", "expected_count"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} cannot be negative")
        if (
            self.observed_count is not None
            and self.expected_count is not None
            and self.observed_count > self.expected_count
        ):
            raise ValueError("observed_count cannot exceed expected_count")
        if self.scope is CoverageScope.NONE and self.observed_count not in (None, 0):
            raise ValueError("NONE coverage cannot contain observed records")

    @property
    def observed_fraction(self) -> float | None:
        """Return a measured fraction only when a non-zero denominator is known."""

        if self.observed_count is None or not self.expected_count:
            return None
        return self.observed_count / self.expected_count

    @classmethod
    def unknown(cls) -> CoverageDimension:
        return cls(scope=CoverageScope.UNKNOWN)


@dataclass(frozen=True, slots=True)
class CoverageProfile:
    """Multidimensional source coverage for a tournament observation."""

    decklists: CoverageDimension = field(default_factory=CoverageDimension.unknown)
    standings: CoverageDimension = field(default_factory=CoverageDimension.unknown)
    matches: CoverageDimension = field(default_factory=CoverageDimension.unknown)


@dataclass(frozen=True, slots=True)
class Provenance:
    """Enough source identity to audit and rebuild one normalized fact."""

    source: str
    source_record_id: str
    retrieved_at: datetime
    parser_version: str
    raw_snapshot_ref: str

    def __post_init__(self) -> None:
        for field_name in ("source", "source_record_id", "parser_version", "raw_snapshot_ref"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be blank")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class OracleCard:
    """A canonical game object used as the scoring identity."""

    oracle_id: str
    name: str

    def __post_init__(self) -> None:
        if not self.oracle_id.strip() or not self.name.strip():
            raise ValueError("oracle_id and name cannot be blank")


@dataclass(frozen=True, slots=True)
class CardPrinting:
    """A printing retained for set, rarity, and Forge-availability filters."""

    scryfall_id: str
    oracle_id: str
    set_code: str
    collector_number: str
    rarity: str
    released_on: date | None = None

    def __post_init__(self) -> None:
        for field_name in ("scryfall_id", "oracle_id", "set_code", "collector_number", "rarity"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be blank")


@dataclass(frozen=True, slots=True)
class Tournament:
    """A tournament as observed by one source snapshot."""

    provenance: Provenance
    occurred_on: date
    format_name: str
    coverage: CoverageProfile
    player_count: int | None = None
    ended_on: date | None = None
    source_format_name: str | None = None

    def __post_init__(self) -> None:
        if not self.format_name.strip():
            raise ValueError("format_name cannot be blank")
        if self.player_count is not None and self.player_count <= 0:
            raise ValueError("player_count must be positive when known")
        if self.ended_on is not None and self.ended_on < self.occurred_on:
            raise ValueError("ended_on cannot precede occurred_on")

    @property
    def source_event_id(self) -> str:
        return self.provenance.source_record_id


@dataclass(frozen=True, slots=True)
class DeckCard:
    """A canonical card observation inside a registered deck."""

    oracle_id: str
    name: str
    mainboard_count: int = 0
    sideboard_count: int = 0

    def __post_init__(self) -> None:
        if not self.oracle_id.strip() or not self.name.strip():
            raise ValueError("oracle_id and name cannot be blank")
        if self.mainboard_count < 0 or self.sideboard_count < 0:
            raise ValueError("card counts cannot be negative")
        if self.mainboard_count + self.sideboard_count == 0:
            raise ValueError("a DeckCard must represent at least one copy")

    @property
    def total_count(self) -> int:
        return self.mainboard_count + self.sideboard_count


@dataclass(frozen=True, slots=True)
class DeckEntry:
    """One registered deck, independent of standings and match results."""

    provenance: Provenance
    source_event_id: str
    cards: tuple[DeckCard, ...]
    player_name: str | None = None

    def __post_init__(self) -> None:
        if not self.source_event_id.strip():
            raise ValueError("source_event_id cannot be blank")
        oracle_ids = [card.oracle_id for card in self.cards]
        if len(oracle_ids) != len(set(oracle_ids)):
            raise ValueError("cards must contain at most one entry per oracle_id")

    @property
    def source_deck_id(self) -> str:
        return self.provenance.source_record_id


@dataclass(frozen=True, slots=True)
class Standing:
    """A source-reported tournament standing for a registered deck."""

    provenance: Provenance
    source_event_id: str
    source_deck_id: str
    final_rank: int | None = None
    wins: int | None = None
    losses: int | None = None
    draws: int | None = None
    byes: int | None = None

    def __post_init__(self) -> None:
        if not self.source_event_id.strip() or not self.source_deck_id.strip():
            raise ValueError("source event and deck identifiers cannot be blank")
        if self.final_rank is not None and self.final_rank <= 0:
            raise ValueError("final_rank must be positive when known")
        for field_name in ("wins", "losses", "draws", "byes"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} cannot be negative")

    @property
    def recorded_matches(self) -> int | None:
        values = (self.wins, self.losses, self.draws)
        if all(value is None for value in values):
            return None
        return sum(value or 0 for value in values)


class MatchResult(StrEnum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"
    BYE = "bye"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MatchParticipant:
    source_deck_id: str
    result: MatchResult
    games_won: int | None = None

    def __post_init__(self) -> None:
        if not self.source_deck_id.strip():
            raise ValueError("source_deck_id cannot be blank")
        if self.games_won is not None and self.games_won < 0:
            raise ValueError("games_won cannot be negative")


@dataclass(frozen=True, slots=True)
class Match:
    """A round-level result; supports one-on-one matches, pods, and byes."""

    provenance: Provenance
    source_event_id: str
    participants: tuple[MatchParticipant, ...]
    round_number: int | None = None
    table_number: int | None = None

    def __post_init__(self) -> None:
        if not self.source_event_id.strip():
            raise ValueError("source_event_id cannot be blank")
        if not self.participants:
            raise ValueError("a match must contain at least one participant")
        participant_ids = [participant.source_deck_id for participant in self.participants]
        if len(participant_ids) != len(set(participant_ids)):
            raise ValueError("match participants must be unique")
        for field_name in ("round_number", "table_number"):
            value = getattr(self, field_name)
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be positive when known")
