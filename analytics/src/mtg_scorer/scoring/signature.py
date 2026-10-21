"""Signature score: how much a card belongs to one strategy, as a 0-100 percentile.

Where the constructed score asks how well a card's decks do, this asks how distinctive
the card is. Three components describe each card against its field: focus (how few
archetypes its decks spread over), reliance (how much more often its home archetype
plays it than decks overall do) and win rate. A staple played everywhere has low focus
and little reliance however strong it is; a card most of one archetype plays, and that
little else does, has both.

Focus is the chance that two of the card's decks share an archetype label. It and the
home archetype's adoption are first pulled toward the field by a prior worth a fixed
number of decks, so two decks of one archetype are weak evidence and a one-list
archetype cannot make every card in it a signature. Each component becomes a
percentile among the scored cards, the percentiles are blended by weight, and the
blend becomes a percentile again: 50 is the median scored card.
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
class SignatureConfig:
    """Component weights and the prior strengths that shrink small samples."""

    version: str = "signature-score-v1"
    focus_weight: float = 0.50
    reliance_weight: float = 0.30
    win_rate_weight: float = 0.20
    # Decks of field-like evidence added to every card's focus and adoption.
    focus_prior_decks: float = 10.0
    adoption_prior_decks: float = 10.0
    # Games of field-average evidence added to every card's win rate.
    win_rate_prior_games: float = 60.0

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("version cannot be blank")
        weights = (self.focus_weight, self.reliance_weight, self.win_rate_weight)
        if any(weight < 0 for weight in weights) or abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("weights must be non-negative and sum to 1")
        priors = (self.focus_prior_decks, self.adoption_prior_decks, self.win_rate_prior_games)
        if any(prior < 0 for prior in priors):
            raise ValueError("prior strengths cannot be negative")

    @property
    def fingerprint(self) -> str:
        return config_fingerprint(self)


@dataclass(frozen=True, slots=True)
class SignatureMethod:
    """Blend shrunk archetype focus, home-archetype reliance and shrunk win rate.

    A card none of whose decks carry an archetype label has no signature score: without
    labels its spread across strategies is unknown, not zero. A missing win rate is left
    out of the card's blend and the other weights are scaled up.
    """

    config: SignatureConfig = SignatureConfig()

    method_id: ClassVar[str] = "signature-score"
    label: ClassVar[str] = "Signature score"
    description: ClassVar[str] = (
        "0-100. Rewards cards that stay in few archetypes (50%), that their home archetype "
        "plays far more often than other decks do (30%) and whose decks win (20%), so "
        "staples played everywhere rank low. Small samples are pulled toward the field, "
        "and 50 is the median ranked card."
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
        focus: dict[str, float] = {}
        adoption: dict[str, float] = {}
        reliance: dict[str, float] = {}
        win_delta: dict[str, float] = {}
        for card in cards:
            features = card.features
            home = features.archetype_adoption
            if not home.is_known:
                continue
            field_focus = features.field_archetype_concentration
            if field_focus is not None:
                # Fewer than two labelled decks say nothing yet, so the card starts at
                # the field's concentration: a card with no preference among archetypes.
                observed = features.archetype_concentration
                decks = observed.support if observed.is_known else 0
                weighted = (observed.value or 0.0) * decks
                focus[card.card_id] = (weighted + config.focus_prior_decks * field_focus) / (
                    decks + config.focus_prior_decks
                )
            # Adoption is pulled toward how often the card is played anywhere, and
            # reliance is how far above that its home archetype plays it.
            played = features.incidence.value or 0.0
            adoption[card.card_id] = (home.support + config.adoption_prior_decks * played) / (
                (home.opportunity_count or 0) + config.adoption_prior_decks
            )
            reliance[card.card_id] = adoption[card.card_id] - played
            field_win, win_rate = features.field_win_rate, features.win_rate.value
            if win_rate is not None and field_win is not None:
                games = features.win_rate.support
                points = win_rate * games
                shrunk = (points + config.win_rate_prior_games * field_win) / (
                    games + config.win_rate_prior_games
                )
                win_delta[card.card_id] = shrunk - field_win

        components = (
            (config.focus_weight, percentiles(focus)),
            (config.reliance_weight, percentiles(reliance)),
            (config.win_rate_weight, percentiles(win_delta)),
        )
        blend: dict[str, float] = {}
        for card_id in adoption:
            known = [(weight, ranks[card_id]) for weight, ranks in components if card_id in ranks]
            total = sum(weight for weight, _ in known)
            if total:
                blend[card_id] = sum(weight * rank for weight, rank in known) / total
        final = percentiles(blend)

        def rounded(value: float | None, digits: int) -> float | None:
            return None if value is None else round(value, digits)

        def archetypes(card_id: str) -> float | None:
            # The number of equally played archetypes that would give the same focus.
            value = focus.get(card_id)
            return rounded(1.0 / value, 2) if value else None

        scores = (
            CardScore(
                card.card_id,
                {
                    "score": rounded(100.0 * final[card.card_id], 3)
                    if card.card_id in final
                    else None
                },
                {
                    "focus": rounded(focus.get(card.card_id), 4),
                    "effective_archetypes": archetypes(card.card_id),
                    "adoption": rounded(adoption.get(card.card_id), 4),
                    "reliance": rounded(reliance.get(card.card_id), 4),
                    "win_rate_delta": rounded(win_delta.get(card.card_id), 4),
                    "blend": rounded(blend.get(card.card_id), 4),
                },
            )
            for card in cards
        )
        return build_run(self, context, scores)
