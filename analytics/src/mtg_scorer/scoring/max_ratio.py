"""Relative volume: each card's count as a share of the largest count it is scored with."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from .base import CardScore, ScoreContext, ScoreRun, ScoringInput, build_run, config_fingerprint

COUNT_MEASURES = ("deck_count", "event_count", "full_field_match_count")


@dataclass(frozen=True, slots=True)
class MaxRatioConfig:
    """Which population count to compare, under a version label."""

    version: str = "max-ratio-v1"
    measure: str = "deck_count"

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("version cannot be blank")
        if self.measure not in COUNT_MEASURES:
            raise ValueError(
                f"measure must be one of {', '.join(COUNT_MEASURES)}; got {self.measure!r}"
            )

    @property
    def fingerprint(self) -> str:
        return config_fingerprint(self)


@dataclass(frozen=True, slots=True)
class MaxRatioMethod:
    """Score 100 for the largest count and the ratio to it for every other card.

    Deliberately simple and descriptive: it measures volume, not quality. Scores are
    relative to the cards passed in, so they move whenever the leading card changes.
    Choose that population before scoring, e.g. exclude basic lands.
    """

    config: MaxRatioConfig = MaxRatioConfig()

    method_id: ClassVar[str] = "max-ratio"
    label: ClassVar[str] = "Relative volume"
    description: ClassVar[str] = (
        "A card's count divided by the largest count among the scored cards, times 100. "
        "If the leading card has 20, a card with 19 scores 95."
    )
    outputs: ClassVar[tuple[str, ...]] = ("max_ratio",)

    @property
    def version(self) -> str:
        return self.config.version

    @property
    def config_hash(self) -> str:
        return self.config.fingerprint

    def score(self, cards: Sequence[ScoringInput], context: ScoreContext) -> ScoreRun:
        counts = [(card.card_id, getattr(card.features, self.config.measure)) for card in cards]
        leader = max((count for _, count in counts), default=0)
        # With no counts at all the ratio is undefined: unknown, not zero.
        scores = (
            CardScore(
                card_id,
                {"max_ratio": round(100.0 * count / leader, 1) if leader else None},
                {"count": count, "max_count": leader},
            )
            for card_id, count in counts
        )
        return build_run(self, context, scores)
