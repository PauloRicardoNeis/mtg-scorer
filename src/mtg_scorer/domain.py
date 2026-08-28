"""Source-independent domain types for historical MTG evidence.

Adapters should translate source-specific payloads into these types. Nothing in this
module should know how TopDeck, MTGTop8, Scryfall, or any future source represents
the same concept.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date
from enum import StrEnum


class CoverageQuality(StrEnum):
    """How completely a source describes the field of an event."""

    FULL_FIELD = "full_field"
    FULL_FIELD_PARTIAL_MATCHES = "full_field_partial_matches"
    TOP_CUT_ONLY = "top_cut_only"
    WINNING_DECKS_ONLY = "winning_decks_only"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Tournament:
    """A tournament as observed by one source."""

    source: str
    source_event_id: str
    occurred_on: date
    format: str
    coverage_quality: CoverageQuality
    player_count: int | None = None

    def __post_init__(self) -> None:
        if self.player_count is not None and self.player_count <= 0:
            raise ValueError("player_count must be positive when known")


@dataclass(frozen=True, slots=True)
class DeckCard:
    """A canonical card observation inside a registered deck.

    `oracle_id` should ultimately be populated from Scryfall so different printings
    of the same game object collapse to one analytical identity.
    """

    oracle_id: str
    name: str
    mainboard_count: int = 0
    sideboard_count: int = 0

    def __post_init__(self) -> None:
        if self.mainboard_count < 0 or self.sideboard_count < 0:
            raise ValueError("card counts cannot be negative")
        if self.mainboard_count + self.sideboard_count == 0:
            raise ValueError("a DeckCard must represent at least one copy")

    @property
    def total_count(self) -> int:
        return self.mainboard_count + self.sideboard_count


@dataclass(frozen=True, slots=True)
class DeckEntry:
    """One player's deck and result at one tournament."""

    source_deck_id: str
    source_event_id: str
    cards: tuple[DeckCard, ...]
    player_name: str | None = None
    final_rank: int | None = None
    wins: int | None = None
    losses: int | None = None
    draws: int | None = None

    def __post_init__(self) -> None:
        if self.final_rank is not None and self.final_rank <= 0:
            raise ValueError("final_rank must be positive when known")
        for field_name in ("wins", "losses", "draws"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} cannot be negative")

    @property
    def recorded_matches(self) -> int | None:
        values = (self.wins, self.losses, self.draws)
        if all(value is None for value in values):
            return None
        return sum(value or 0 for value in values)


@dataclass(frozen=True, slots=True)
class CardFeatures:
    """Normalized analytical features consumed by scoring models.

    Unit-interval fields are intentionally semantic rather than source-specific.
    They are expected to be produced by a later feature-computation layer.

    Counts remain raw because evidence/confidence should respond to the amount of
    supporting data independently of the substantive Engine/Staple estimate.
    """

    # Staple-oriented features.
    incidence: float
    archetype_breadth: float
    format_era_breadth: float

    # Shared / engine-oriented features.
    competitive_proof: float
    commitment: float
    specificity: float
    package_coherence: float
    repeat_evidence: float
    choice_freedom: float

    # Confidence-oriented features.
    coverage_strength: float
    deck_count: int
    event_count: int
    full_field_matches: int = 0

    def __post_init__(self) -> None:
        unit_interval_fields = (
            "incidence",
            "archetype_breadth",
            "format_era_breadth",
            "competitive_proof",
            "commitment",
            "specificity",
            "package_coherence",
            "repeat_evidence",
            "choice_freedom",
            "coverage_strength",
        )
        for field_name in unit_interval_fields:
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1; got {value}")

        for field_name in ("deck_count", "event_count", "full_field_matches"):
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative")

    @classmethod
    def empty(cls) -> CardFeatures:
        """Return a no-evidence feature vector useful for baselines and tests."""

        numeric_fields = {field.name: 0 for field in fields(cls)}
        return cls(**numeric_fields)
