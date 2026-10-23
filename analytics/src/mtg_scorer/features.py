"""Missing-aware analytical features produced from normalized historical facts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FeatureObservation:
    """A normalized estimate together with the data that supports it.

    ``value=None`` means unavailable, not zero. ``support`` is the number of
    observations contributing to the estimate. ``opportunity_count``
    records an eligible denominator when the feature has one.
    """

    value: float | None
    support: int = 0
    opportunity_count: int | None = None

    def __post_init__(self) -> None:
        if self.value is not None and not 0.0 <= self.value <= 1.0:
            raise ValueError(f"feature value must be between 0 and 1; got {self.value}")
        if self.support < 0:
            raise ValueError("support cannot be negative")
        if self.opportunity_count is not None and self.opportunity_count < 0:
            raise ValueError("opportunity_count cannot be negative")
        if self.opportunity_count is not None and self.support > self.opportunity_count:
            raise ValueError("support cannot exceed opportunity_count")

    @property
    def is_known(self) -> bool:
        return self.value is not None

    @classmethod
    def unknown(cls) -> FeatureObservation:
        return cls(value=None)

    @classmethod
    def known(
        cls,
        value: float,
        *,
        support: int = 0,
        opportunity_count: int | None = None,
    ) -> FeatureObservation:
        return cls(value=value, support=support, opportunity_count=opportunity_count)


@dataclass(frozen=True, slots=True)
class CardFeatures:
    """Feature vector consumed by a versioned score model."""

    incidence: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    deck_family_breadth: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    format_era_breadth: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    competitive_proof: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    commitment: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    specificity: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    package_coherence: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    recurrence: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    choice_freedom: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    coverage_strength: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    # Match points per game of the card's decks; support is the games played.
    win_rate: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    # Share of the card's decks with a known result that made the top cut.
    top_cut_rate: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    # The chance that two of the card's labelled decks share an archetype label;
    # support is its labelled decks.
    archetype_concentration: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    # Share of the decks of the card's most common archetype that play it.
    archetype_adoption: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    # Share of the card's decks that play a full playset of it in the mainboard; support
    # is those decks and the opportunity all of the card's decks.
    playset_rate: FeatureObservation = field(default_factory=FeatureObservation.unknown)
    # The whole cohort's rates, which the card's are compared with.
    field_win_rate: float | None = None
    field_top_cut_rate: float | None = None
    field_archetype_concentration: float | None = None
    deck_count: int = 0
    event_count: int = 0
    full_field_match_count: int = 0

    def __post_init__(self) -> None:
        for field_name in ("deck_count", "event_count", "full_field_match_count"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")
        for field_name in ("field_win_rate", "field_top_cut_rate", "field_archetype_concentration"):
            value = getattr(self, field_name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1; got {value}")

    @classmethod
    def empty(cls) -> CardFeatures:
        return cls()
