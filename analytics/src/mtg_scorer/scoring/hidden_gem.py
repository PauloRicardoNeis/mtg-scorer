"""Hidden gem score: uncommon cards that the decks playing them build around and win with.

Where the constructed score asks how well a card's decks do and the signature score how
much it belongs to one strategy, this looks for cards almost nobody plays that still
earn their place: a deck that plays one plays a full playset, and those decks beat the
field. Four factors are multiplied, so a card needs all of them:

- playsets: the share of its decks that play four copies, pulled toward the field's
  share by a prior worth a few decks;
- results: how far its decks' win rate and top-cut conversion, each pulled toward the
  field by a prior, rise above the field's, as a relative lift;
- recurrence: how many events it was seen at, so one deck's lucky weekend stays an
  anecdote;
- rarity: a discount on its meta share that halves the score of a card in 2% of decks
  and leaves a staple little.

Unlike the other methods' percentile blends, the factors keep their magnitudes until
the end: among thousands of cards seen once or twice, a percentile would turn a tiny
lucky edge into a high rank. Cards whose decks do no better than the field score 0; the
rest become percentiles among themselves, so 50 is the median card that looks like a
gem at all. In a singleton format nothing is a playset, so no card has a score.
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
class HiddenGemConfig:
    """Result weights, the priors that shrink small samples and each factor's half point."""

    version: str = "hidden-gem-score-v1"
    win_rate_weight: float = 0.70
    top_cut_weight: float = 0.30
    # Decks of field-like evidence added to every card's playset share.
    playset_prior_decks: float = 5.0
    # Games and decks of field-average evidence added to every card's results; stronger
    # than the constructed score's, since gems come from the tail, where luck gathers.
    win_rate_prior_games: float = 100.0
    top_cut_prior_decks: float = 20.0
    # The events at which a card earns half its recurrence, and the meta share at which
    # the rarity discount halves its score.
    half_recurrence_events: float = 2.0
    half_score_share: float = 0.02
    # Below this share of playsets among the scored cards' decks the format is singleton,
    # and copies say nothing about a card.
    min_field_playset_rate: float = 0.05

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("version cannot be blank")
        weights = (self.win_rate_weight, self.top_cut_weight)
        if any(weight < 0 for weight in weights) or abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("weights must be non-negative and sum to 1")
        priors = (self.playset_prior_decks, self.win_rate_prior_games, self.top_cut_prior_decks)
        if any(prior < 0 for prior in priors) or self.half_recurrence_events < 0:
            raise ValueError("prior strengths and half points cannot be negative")
        if self.half_score_share <= 0:
            raise ValueError("half_score_share must be positive")
        if not 0.0 <= self.min_field_playset_rate <= 1.0:
            raise ValueError("min_field_playset_rate must be between 0 and 1")

    @property
    def fingerprint(self) -> str:
        return config_fingerprint(self)


@dataclass(frozen=True, slots=True)
class HiddenGemMethod:
    """Multiply shrunk playset share, shrunk result lift, recurrence and a rarity discount.

    A result unknown for a card (no recorded matches, no known top cuts) is left out of
    its lift and the other weight is scaled up; a card with neither has no score. Nor
    does any card of a cohort with too few playsets to tell a build-around from a 1-of.
    """

    config: HiddenGemConfig = HiddenGemConfig()

    method_id: ClassVar[str] = "hidden-gem-score"
    label: ClassVar[str] = "Hidden gem score"
    description: ClassVar[str] = (
        "0-100. Finds cards few decks play but that the decks playing them build around and "
        "win with. Multiplies how often a card is played as a four-of, how far its decks beat "
        "the field's win rate (70%) and top-cut conversion (30%) and how many events it "
        "recurs at, then discounts by meta share: a card in 2% of decks keeps half its score "
        "and staples keep little. Small samples are pulled toward the field. Cards whose "
        "decks do no better than the field score 0 and 50 is the median of the rest; "
        "singleton formats have no score."
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
        observed = [card.features.playset_rate for card in cards]
        decks = sum(o.opportunity_count or 0 for o in observed if o.is_known)
        field_playsets = sum(o.support for o in observed if o.is_known) / decks if decks else 0.0
        singleton = field_playsets < config.min_field_playset_rate

        playsets: dict[str, float] = {}
        win_lift: dict[str, float] = {}
        cut_lift: dict[str, float] = {}
        lift: dict[str, float] = {}
        recurrence: dict[str, float] = {}
        rarity: dict[str, float] = {}
        gem: dict[str, float] = {}
        for card in () if singleton else cards:
            features = card.features
            incidence = features.incidence.value
            if not features.playset_rate.is_known or incidence is None:
                continue
            field_win, win_rate = features.field_win_rate, features.win_rate.value
            if win_rate is not None and field_win:
                games = features.win_rate.support
                points = win_rate * games
                shrunk = (points + config.win_rate_prior_games * field_win) / (
                    games + config.win_rate_prior_games
                )
                win_lift[card.card_id] = shrunk / field_win - 1
            field_cut, cut_rate = features.field_top_cut_rate, features.top_cut_rate.value
            if cut_rate is not None and field_cut:
                known = features.top_cut_rate.support
                made = cut_rate * known
                shrunk = (made + config.top_cut_prior_decks * field_cut) / (
                    known + config.top_cut_prior_decks
                )
                cut_lift[card.card_id] = shrunk / field_cut - 1
            results = [
                (weight, lifts[card.card_id])
                for weight, lifts in (
                    (config.win_rate_weight, win_lift),
                    (config.top_cut_weight, cut_lift),
                )
                if card.card_id in lifts
            ]
            total = sum(weight for weight, _ in results)
            if not total:
                continue
            lift[card.card_id] = sum(weight * value for weight, value in results) / total
            # A card's playset share is pulled toward the field's, so a single four-of
            # deck is only a little more committed than the field.
            own = features.playset_rate
            playsets[card.card_id] = (own.support + config.playset_prior_decks * field_playsets) / (
                (own.opportunity_count or 0) + config.playset_prior_decks
            )
            events = features.event_count
            recurrence[card.card_id] = (
                events / (events + config.half_recurrence_events) if events else 0.0
            )
            rarity[card.card_id] = 1.0 / (1.0 + incidence / config.half_score_share)
            gem[card.card_id] = (
                playsets[card.card_id]
                * lift[card.card_id]
                * recurrence[card.card_id]
                * rarity[card.card_id]
            )
        ranks = percentiles({card_id: value for card_id, value in gem.items() if value > 0})

        def rounded(value: float | None, digits: int) -> float | None:
            return None if value is None else round(value, digits)

        def final(card_id: str) -> float | None:
            if card_id in ranks:
                return rounded(100.0 * ranks[card_id], 3)
            return 0.0 if card_id in gem else None

        scores = (
            CardScore(
                card.card_id,
                {"score": final(card.card_id)},
                {
                    "playset_rate": rounded(playsets.get(card.card_id), 4),
                    "win_rate_lift": rounded(win_lift.get(card.card_id), 4),
                    "top_cut_lift": rounded(cut_lift.get(card.card_id), 4),
                    "result_lift": rounded(lift.get(card.card_id), 4),
                    "recurrence": rounded(recurrence.get(card.card_id), 4),
                    "rarity": rounded(rarity.get(card.card_id), 4),
                    "gem": rounded(gem.get(card.card_id), 6),
                },
            )
            for card in cards
        )
        return build_run(self, context, scores)
