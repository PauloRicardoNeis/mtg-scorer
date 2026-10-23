"""The constructed score blends shrunk win rate, top-cut conversion and meta share."""

import pytest

from mtg_scorer import CardFeatures, FeatureObservation, ScoreContext, ScoringInput
from mtg_scorer.scoring import ConstructedConfig, ConstructedMethod

CONTEXT = ScoreContext(dataset_snapshot_id="fixture", feature_pipeline_version="test-v1")
METHOD = ConstructedMethod()


def card(card_id, *, share=0.1, win=None, games=0, cut=None, known=0, field_cut=0.25):
    return ScoringInput(
        card_id,
        CardFeatures(
            incidence=FeatureObservation.known(share, support=10, opportunity_count=100),
            win_rate=(
                FeatureObservation.unknown()
                if win is None
                else FeatureObservation.known(win, support=games)
            ),
            top_cut_rate=(
                FeatureObservation.unknown()
                if cut is None
                else FeatureObservation.known(cut, support=known, opportunity_count=known)
            ),
            field_win_rate=0.5,
            field_top_cut_rate=field_cut,
            deck_count=10,
            event_count=2,
        ),
    )


def scores(cards):
    return {s.card_id: s.values["score"] for s in METHOD.score(cards, CONTEXT).scores}


def test_a_better_win_rate_scores_higher_when_all_else_is_equal() -> None:
    result = scores(
        [
            card("a", win=0.6, games=200),
            card("b", win=0.5, games=200),
            card("c", win=0.4, games=200),
        ]
    )

    assert result["a"] > result["b"] > result["c"]


def test_the_median_card_scores_50() -> None:
    result = scores([card(c, win=w, games=100) for c, w in (("a", 0.4), ("b", 0.5), ("c", 0.6))])

    assert result["b"] == 50.0


def test_a_tiny_sample_is_pulled_toward_the_field() -> None:
    # Two wins in two games is less evidence than 60% over two hundred games.
    result = scores([card("lucky", win=1.0, games=2), card("proven", win=0.6, games=200)])

    assert result["proven"] > result["lucky"]


def test_a_card_without_a_record_is_blended_from_what_is_known() -> None:
    run = METHOD.score([card("a", share=0.5), card("b", share=0.1, win=0.6, games=50)], CONTEXT)
    by_id = {s.card_id: s for s in run.scores}

    assert by_id["a"].inputs["win_rate_delta"] is None
    assert by_id["a"].values["score"] is not None


def test_top_cut_conversion_is_compared_with_the_field() -> None:
    run = METHOD.score([card("a", cut=0.5, known=100), card("b", cut=0.1, known=100)], CONTEXT)
    lifts = {s.card_id: s.inputs["top_cut_lift"] for s in run.scores}

    assert lifts["a"] > 1.0 > lifts["b"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"win_rate_weight": 0.7}, "weights must be non-negative and sum to 1"),
        ({"share_weight": -0.1, "win_rate_weight": 0.75}, "weights must be non-negative"),
        ({"version": " "}, "version cannot be blank"),
    ],
)
def test_the_config_rejects_unusable_settings(changes, message) -> None:
    with pytest.raises(ValueError, match=message):
        ConstructedConfig(**changes)
