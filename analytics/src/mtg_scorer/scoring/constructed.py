"""Constructed score: how well a card's decks perform, as a 0-100 percentile.

Three components describe each card against its field: match win rate, top-cut
conversion and meta share. Win rate and conversion are first pulled toward the
field by a prior worth a fixed number of games or decks, so a card seen in two
decks cannot outrank one seen in two hundred. Each component then becomes a
percentile among the scored cards, the percentiles are blended by weight, and the
blend becomes a percentile again: 50 is the median scored card. Scores keep three
decimals so a large population does not tie whole rows of cards.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from .base import (
    CardScore,
    ScoreContext,
    ScoreRun,
    ScoringInput,
    build_run,
    config_fingerprint,
    percentiles,
)


@dataclass(frozen=True, slots=True)
class ConstructedConfig:
    """Component weights and the prior strengths that shrink small samples."""

    version: str = "constructed-score-v1"
    win_rate_weight: float = 0.60
    top_cut_weight: float = 0.25
    share_weight: float = 0.15
    # Games and decks of field-average evidence added to every card.
    win_rate_prior_games: float = 60.0
    top_cut_prior_decks: float = 20.0

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("version cannot be blank")
        weights = (self.win_rate_weight, self.top_cut_weight, self.share_weight)
        if any(weight < 0 for weight in weights) or abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("weights must be non-negative and sum to 1")
        if self.win_rate_prior_games < 0 or self.top_cut_prior_decks < 0:
            raise ValueError("prior strengths cannot be negative")

    @property
    def fingerprint(self) -> str:
        return config_fingerprint(self)


@dataclass(frozen=True, slots=True)
class ConstructedMethod:
    """Blend shrunk win rate, shrunk top-cut conversion and meta share into a percentile.

    A component unknown for a card (no recorded matches, no known top cuts) is left out
    of that card's blend and the other weights are scaled up, so a missing record
    neither helps nor hurts it.
    """

    config: ConstructedConfig = ConstructedConfig()

    method_id: ClassVar[str] = "constructed-score"
    label: ClassVar[str] = "Constructed score"
    description: ClassVar[str] = (
        "0-100. Blends win rate against the field (60%), top-cut conversion (25%) and "
        "meta share (15%). Small samples are pulled toward the field average, and 50 is "
        "the median ranked card."
    )
    outputs: ClassVar[tuple[str, ...]] = ("score",)

    @property
    def version(self) -> str:
        return self.config.version

    @property
    def config_hash(self) -> str:
        return self.config.fingerprint

    def score(self, cards: Sequence[ScoringInput], context: ScoreContext) -> ScoreRun:
        config = self.config
        win_delta: dict[str, float] = {}
        cut_lift: dict[str, float] = {}
        share: dict[str, float] = {}
        for card in cards:
            features = card.features
            field_win, win_rate = features.field_win_rate, features.win_rate.value
            if win_rate is not None and field_win is not None:
                games = features.win_rate.support
                points = win_rate * games
                shrunk = (points + config.win_rate_prior_games * field_win) / (
                    games + config.win_rate_prior_games
                )
                win_delta[card.card_id] = shrunk - field_win
            field_cut, cut_rate = features.field_top_cut_rate, features.top_cut_rate.value
            if cut_rate is not None and field_cut:
                known = features.top_cut_rate.support
                made = cut_rate * known
                shrunk = (made + config.top_cut_prior_decks * field_cut) / (
                    known + config.top_cut_prior_decks
                )
                cut_lift[card.card_id] = shrunk / field_cut
            if (incidence := features.incidence.value) is not None:
                share[card.card_id] = incidence

        components = (
            (config.win_rate_weight, percentiles(win_delta)),
            (config.top_cut_weight, percentiles(cut_lift)),
            (config.share_weight, percentiles(share)),
        )
        blend: dict[str, float] = {}
        for card in cards:
            known = [
                (weight, ranks[card.card_id])
                for weight, ranks in components
                if card.card_id in ranks
            ]
            total = sum(weight for weight, _ in known)
            if total:
                blend[card.card_id] = sum(weight * rank for weight, rank in known) / total
        final = percentiles(blend)

        def rounded(value: float | None, digits: int) -> float | None:
            return None if value is None else round(value, digits)

        scores = (
            CardScore(
                card.card_id,
                {
                    "score": rounded(100.0 * final[card.card_id], 3)
                    if card.card_id in final
                    else None
                },
                {
                    "win_rate_delta": rounded(win_delta.get(card.card_id), 4),
                    "top_cut_lift": rounded(cut_lift.get(card.card_id), 4),
                    "meta_share": rounded(share.get(card.card_id), 4),
                    "blend": rounded(blend.get(card.card_id), 4),
                },
            )
            for card in cards
        )
        return build_run(self, context, scores)
