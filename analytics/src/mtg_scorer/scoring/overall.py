"""Overall grade: one 0-100 percentile per card from its grades in every format.

Each format's run grades its own cards against its own field, so a card's per-format
scores are already comparable percentiles. The overall grade averages them, with two
adjustments. A format counts by its evidence: one with a few dozen decklists barely
moves a card, while every format with thousands counts the same. And every card also
carries one format's worth of a median score, so a card proven across many formats
outranks one that is strong in a single format. The average then becomes a percentile
again among every graded card: 50 is the median card ranked in any format.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar

from .base import CardScore, config_fingerprint, percentiles


@dataclass(frozen=True, slots=True)
class OverallConfig:
    """Which per-format output to combine, and how evidence and the prior weigh it."""

    version: str = "overall-grade-v1"
    component_method: str = "constructed-score"
    component_output: str = "score"
    # A format with this many decklists counts half as much as an unlimited one.
    half_weight_decks: float = 250.0
    # Formats' worth of a median score added to every card.
    prior_formats: float = 1.0
    prior_score: float = 50.0

    def __post_init__(self) -> None:
        for field_name in ("version", "component_method", "component_output"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be blank")
        if self.half_weight_decks <= 0:
            raise ValueError("half_weight_decks must be positive")
        if self.prior_formats < 0:
            raise ValueError("prior_formats cannot be negative")
        if not 0 <= self.prior_score <= 100:
            raise ValueError("prior_score must be within 0-100")

    @property
    def fingerprint(self) -> str:
        return config_fingerprint(self)


@dataclass(frozen=True, slots=True)
class FormatGrades:
    """One format's run: its decklists and the score of every card it graded."""

    format_name: str
    decks: int
    scores: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.format_name.strip():
            raise ValueError("format_name cannot be blank")
        if self.decks < 0:
            raise ValueError("decks cannot be negative")


@dataclass(frozen=True, slots=True)
class OverallMethod:
    """Average a card's per-format scores by format evidence, shrunk toward the median."""

    config: OverallConfig = OverallConfig()

    method_id: ClassVar[str] = "overall-grade"
    label: ClassVar[str] = "Overall grade"
    description: ClassVar[str] = (
        "0-100. Averages the card's constructed score in every format that ranks it. "
        "A format counts by its evidence (one with 250 decklists counts half), and every "
        "card carries one format's worth of a median score, so a card proven across many "
        "formats outranks one strong in a single format. 50 is the median graded card."
    )
    outputs: ClassVar[tuple[str, ...]] = ("score",)

    @property
    def version(self) -> str:
        return self.config.version

    @property
    def config_hash(self) -> str:
        return self.config.fingerprint

    def weight(self, decks: int) -> float:
        """How much one format counts, from 0 without decklists toward 1."""

        return decks / (decks + self.config.half_weight_decks)

    def score(self, formats: Sequence[FormatGrades]) -> tuple[CardScore, ...]:
        """Grade every card that some format graded; formats without decks are ignored."""

        names = [grades.format_name for grades in formats]
        if len(set(names)) != len(names):
            raise ValueError("each format can be combined only once")
        config = self.config
        weighted: dict[str, float] = {}
        evidence: dict[str, float] = {}
        count: dict[str, int] = {}
        for grades in formats:
            weight = self.weight(grades.decks)
            if not weight:
                continue
            for card_id, value in grades.scores.items():
                weighted[card_id] = weighted.get(card_id, 0.0) + weight * value
                evidence[card_id] = evidence.get(card_id, 0.0) + weight
                count[card_id] = count.get(card_id, 0) + 1
        prior = config.prior_formats * config.prior_score
        blend = {
            card_id: (weighted[card_id] + prior) / (evidence[card_id] + config.prior_formats)
            for card_id in weighted
        }
        final = percentiles(blend)
        return tuple(
            CardScore(
                card_id,
                {"score": round(100.0 * final[card_id], 3)},
                {
                    "blend": round(blend[card_id], 4),
                    "evidence": round(evidence[card_id], 4),
                    "formats": float(count[card_id]),
                },
            )
            for card_id in sorted(blend)
        )
