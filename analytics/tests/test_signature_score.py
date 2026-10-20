"""The signature score rewards cards that belong to one archetype, not to every deck."""

import pytest

from mtg_scorer import CardFeatures, FeatureObservation, ScoreContext, ScoringInput
from mtg_scorer.scoring import SignatureConfig, SignatureMethod

CONTEXT = ScoreContext(dataset_snapshot_id="fixture", feature_pipeline_version="test-v1")
METHOD = SignatureMethod()
# A field of many archetypes: two random decks share one 5% of the time.
FIELD_FOCUS = 0.05


def card(
    card_id,
    *,
    labelled=40,
    focus=None,
    home=20,
    home_size=25,
    share=0.1,
    win=None,
    games=0,
):
    """A card with ``labelled`` labelled decks, ``home`` of them in a ``home_size`` archetype."""

    return ScoringInput(
        card_id,
        CardFeatures(
            incidence=FeatureObservation.known(share, support=10, opportunity_count=100),
            archetype_concentration=(
                FeatureObservation.unknown()
                if focus is None
                else FeatureObservation.known(focus, support=labelled)
            ),
            archetype_adoption=(
                FeatureObservation.unknown()
                if home_size == 0
                else FeatureObservation.known(
                    home / home_size, support=home, opportunity_count=home_size
                )
            ),
            win_rate=(
                FeatureObservation.unknown()
                if win is None
                else FeatureObservation.known(win, support=games)
            ),
            field_win_rate=0.5,
            field_archetype_concentration=FIELD_FOCUS,
            deck_count=labelled,
            event_count=4,
        ),
    )


def run(cards):
    return {s.card_id: s for s in METHOD.score(cards, CONTEXT).scores}


def scores(cards):
    return {card_id: s.values["score"] for card_id, s in run(cards).items()}


def test_a_card_in_one_archetype_outranks_one_spread_over_many() -> None:
    result = scores(
        [
            card("engine", focus=0.9),
            card("shared", focus=0.4),
            card("everywhere", focus=0.06),
        ]
    )

    assert result["engine"] > result["shared"] > result["everywhere"]


def test_a_staple_ranks_below_a_card_its_archetype_relies_on() -> None:
    # Both are played by 90% of their home archetype, but the staple is in 60% of all decks.
    result = scores(
        [
            card("staple", focus=0.2, home=18, home_size=20, share=0.6),
            card("engine", focus=0.2, home=18, home_size=20, share=0.05),
            card("filler", focus=0.2, home=2, home_size=20, share=0.05),
        ]
    )

    assert result["engine"] > result["staple"]
    assert result["engine"] > result["filler"]


def test_the_median_card_scores_50() -> None:
    result = scores([card(c, focus=f) for c, f in (("a", 0.2), ("b", 0.5), ("c", 0.8))])

    assert result["b"] == 50.0


def test_two_decks_of_one_archetype_are_weaker_evidence_than_forty() -> None:
    inputs = run(
        [
            card("lucky", labelled=2, focus=1.0, home=2, home_size=2),
            card("proven", labelled=40, focus=0.9, home=36, home_size=40),
        ]
    )

    assert inputs["proven"].inputs["focus"] > inputs["lucky"].inputs["focus"]
    assert inputs["proven"].values["score"] > inputs["lucky"].values["score"]


def test_a_card_with_one_labelled_deck_starts_at_the_field_concentration() -> None:
    single = run([card("single", labelled=1, focus=None, home=1, home_size=30)])["single"]

    assert single.inputs["focus"] == FIELD_FOCUS
    assert single.inputs["effective_archetypes"] == 1 / FIELD_FOCUS
    assert single.values["score"] is not None


def test_effective_archetypes_is_the_inverse_of_focus() -> None:
    inputs = run([card("a", labelled=90, focus=0.55)])["a"].inputs

    assert inputs["effective_archetypes"] == pytest.approx(1 / inputs["focus"], abs=0.01)


def test_a_card_without_labelled_decks_has_no_signature_score() -> None:
    result = run([card("unlabelled", home_size=0, win=0.7, games=200), card("a", focus=0.5)])

    assert result["unlabelled"].values["score"] is None
    assert set(result["unlabelled"].inputs.values()) == {None}
    assert result["a"].values["score"] == 50.0


def test_among_equally_distinctive_cards_the_winning_one_scores_higher() -> None:
    result = scores(
        [
            card("winner", focus=0.6, win=0.58, games=300),
            card("loser", focus=0.6, win=0.44, games=300),
        ]
    )

    assert result["winner"] > result["loser"]


@pytest.mark.parametrize(
    "changes",
    [
        {"focus_weight": 0.6},
        {"reliance_weight": -0.1, "focus_weight": 0.9},
        {"focus_prior_decks": -1.0},
        {"version": " "},
    ],
)
def test_the_config_rejects_unusable_settings(changes) -> None:
    with pytest.raises(ValueError):
        SignatureConfig(**changes)
