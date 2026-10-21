"""The hidden gem score finds cards few decks play but that those decks build around and win
with."""

import pytest

from mtg_scorer import CardFeatures, FeatureObservation, ScoreContext, ScoringInput
from mtg_scorer.scoring import HiddenGemConfig, HiddenGemMethod

CONTEXT = ScoreContext(dataset_snapshot_id="fixture", feature_pipeline_version="test-v1")
METHOD = HiddenGemMethod()


def card(
    card_id,
    *,
    decks=12,
    playsets=12,
    share=0.01,
    events=8,
    win=0.6,
    games=100,
    cut=None,
    cut_known=0,
):
    """A card in ``decks`` decks, ``playsets`` of them with four copies, ``share`` of all."""

    return ScoringInput(
        card_id,
        CardFeatures(
            incidence=FeatureObservation.known(share, support=decks, opportunity_count=1000),
            playset_rate=FeatureObservation.known(
                playsets / decks, support=playsets, opportunity_count=decks
            ),
            win_rate=(
                FeatureObservation.unknown()
                if win is None
                else FeatureObservation.known(win, support=games)
            ),
            top_cut_rate=(
                FeatureObservation.unknown()
                if cut is None
                else FeatureObservation.known(cut, support=cut_known, opportunity_count=cut_known)
            ),
            field_win_rate=0.5,
            field_top_cut_rate=0.25,
            deck_count=decks,
            event_count=events,
        ),
    )


def run(cards, method=METHOD):
    return {s.card_id: s for s in method.score(cards, CONTEXT).scores}


def scores(cards):
    return {card_id: s.values["score"] for card_id, s in run(cards).items()}


def test_a_rare_four_of_outranks_a_staple_with_the_same_results() -> None:
    result = scores(
        [
            card("gem", share=0.01),
            card("staple", decks=400, playsets=400, share=0.4, events=40, games=3000),
            card("filler", win=0.53),
        ]
    )

    assert result["gem"] > result["filler"] > result["staple"]


def test_a_card_its_decks_play_four_of_outranks_one_they_play_once() -> None:
    result = scores([card("core", playsets=12), card("tech", playsets=0), card("filler", win=0.51)])

    assert result["core"] > result["tech"]


def test_cards_whose_decks_do_no_better_than_the_field_score_zero() -> None:
    result = run([card("gem"), card("even", win=0.5), card("losing", win=0.4)])

    assert result["even"].values["score"] == 0.0
    assert result["losing"].values["score"] == 0.0
    assert result["losing"].inputs["result_lift"] < 0
    assert result["gem"].values["score"] == 50.0


def test_the_median_of_the_cards_that_beat_the_field_scores_50() -> None:
    result = scores([card(c, win=w) for c, w in (("a", 0.55), ("b", 0.6), ("c", 0.65))])

    assert result["b"] == 50.0
    assert result["a"] < result["b"] < result["c"]


def test_one_lucky_deck_is_weaker_evidence_than_a_card_that_keeps_winning() -> None:
    result = run(
        [
            card("lucky", decks=1, playsets=1, share=0.001, events=1, win=0.9, games=10),
            card("proven", decks=12, playsets=12, share=0.012, events=8, win=0.6, games=100),
            card("tech", playsets=0),
        ]
    )

    assert result["proven"].values["score"] > result["lucky"].values["score"]
    assert result["proven"].inputs["playset_rate"] > result["lucky"].inputs["playset_rate"]
    assert result["proven"].inputs["recurrence"] > result["lucky"].inputs["recurrence"]


def test_each_factor_reaches_half_at_its_configured_point() -> None:
    inputs = run([card("half", share=0.02, events=2)])["half"].inputs

    assert inputs["rarity"] == 0.5
    assert inputs["recurrence"] == 0.5
    assert inputs["gem"] == pytest.approx(
        inputs["playset_rate"] * inputs["result_lift"] * 0.25, abs=1e-4
    )


def test_top_cut_conversion_alone_can_show_success() -> None:
    result = run([card("converts", win=None, cut=0.6, cut_known=10)])["converts"]

    assert result.inputs["win_rate_lift"] is None
    assert result.inputs["result_lift"] == result.inputs["top_cut_lift"] > 0
    assert result.values["score"] == 50.0


def test_a_card_without_known_results_has_no_score() -> None:
    result = run([card("unknown", win=None), card("gem")])

    assert result["unknown"].values["score"] is None
    assert set(result["unknown"].inputs.values()) == {None}
    assert result["gem"].values["score"] == 50.0


def test_a_singleton_format_has_no_hidden_gem_scores() -> None:
    result = run([card("a", playsets=0), card("b", playsets=0, win=0.7)])

    assert {s.values["score"] for s in result.values()} == {None}


def test_a_few_playsets_in_a_singleton_format_do_not_make_it_scoreable() -> None:
    # One Relentless Rats deck among a hundred singleton decks of each card.
    cards = [card(f"c{n}", decks=100, playsets=0) for n in range(9)]
    cards.append(card("rats", decks=100, playsets=1))

    assert {s.values["score"] for s in run(cards).values()} == {None}


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"win_rate_weight": 0.6}, "weights must be non-negative and sum to 1"),
        ({"top_cut_weight": -0.1, "win_rate_weight": 1.1}, "weights must be non-negative"),
        ({"playset_prior_decks": -1.0}, "prior strengths and half points cannot be negative"),
        ({"half_recurrence_events": -1.0}, "prior strengths and half points cannot be negative"),
        ({"half_score_share": 0.0}, "half_score_share must be positive"),
        ({"min_field_playset_rate": 1.5}, "min_field_playset_rate must be between 0 and 1"),
        ({"version": " "}, "version cannot be blank"),
    ],
)
def test_the_config_rejects_unusable_settings(changes, message) -> None:
    with pytest.raises(ValueError, match=message):
        HiddenGemConfig(**changes)
