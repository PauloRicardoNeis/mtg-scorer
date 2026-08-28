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
    deck_count: int = 0
    event_count: int = 0
    full_field_match_count: int = 0

    def __post_init__(self) -> None:
        for field_name in ("deck_count", "event_count", "full_field_match_count"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")

    @classmethod
    def empty(cls) -> CardFeatures:
        return cls()
