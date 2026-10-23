import re
from types import SimpleNamespace

import pytest

from mtg_scorer import (
    SCORE_METHODS,
    CardFeatures,
    CardScore,
    FeatureObservation,
    FoundationMethod,
    MaxRatioConfig,
    MaxRatioMethod,
    ScoreConfig,
    ScoreContext,
    ScoreMethodRegistry,
    ScoreRun,
    ScoringInput,
    score_card,
)
from mtg_scorer.scoring import DEFAULT_CONFIG, build_run

CONTEXT = ScoreContext(
    dataset_snapshot_id="fixture-2026-10-18",
    feature_pipeline_version="test-features-v1",
)

STRATUM = (
    ScoringInput(
        "card-a",
        CardFeatures(
            incidence=FeatureObservation.known(0.6, support=30),
            specificity=FeatureObservation.known(0.2, support=30),
            deck_count=30,
            event_count=6,
            full_field_match_count=120,
        ),
    ),
    ScoringInput(
        "card-b",
        CardFeatures(
            incidence=FeatureObservation.known(0.2, support=10),
            deck_count=10,
            event_count=3,
        ),
    ),
    ScoringInput("card-c", CardFeatures.empty()),
)


def counted(card_id: str, decks: int = 0, events: int = 0) -> ScoringInput:
    return ScoringInput(card_id, CardFeatures(deck_count=decks, event_count=events))


def ratios(run: ScoreRun) -> dict[str, float | None]:
    return {score.card_id: score.values["max_ratio"] for score in run.scores}


# Contract: every registered method, including ones added later, must pass these.


@pytest.mark.parametrize("method", list(SCORE_METHODS), ids=lambda method: method.method_id)
def test_every_method_scores_each_card_once_with_its_declared_outputs(method) -> None:
    run = method.score(STRATUM, CONTEXT)

    assert [score.card_id for score in run.scores] == [card.card_id for card in STRATUM]
    assert all(set(score.values) == set(method.outputs) for score in run.scores)


@pytest.mark.parametrize("method", list(SCORE_METHODS), ids=lambda method: method.method_id)
def test_every_method_run_carries_its_complete_identity(method) -> None:
    run = method.score(STRATUM, CONTEXT)

    assert run.method_id == method.method_id
    assert run.method_version == method.version
    assert run.method_config_hash == method.config_hash
    assert re.fullmatch(r"[0-9a-f]{64}", run.method_config_hash)
    assert run.dataset_snapshot_id == CONTEXT.dataset_snapshot_id
    assert run.feature_pipeline_version == CONTEXT.feature_pipeline_version


@pytest.mark.parametrize("method", list(SCORE_METHODS), ids=lambda method: method.method_id)
def test_every_method_is_deterministic(method) -> None:
    assert method.score(STRATUM, CONTEXT) == method.score(STRATUM, CONTEXT)


@pytest.mark.parametrize("method", list(SCORE_METHODS), ids=lambda method: method.method_id)
def test_every_method_describes_itself_for_a_methodology_page(method) -> None:
    assert method.label.strip()
    assert method.description.strip()
    assert method.version.strip()
    assert method.outputs
    assert len(set(method.outputs)) == len(method.outputs)


@pytest.mark.parametrize("method", list(SCORE_METHODS), ids=lambda method: method.method_id)
def test_every_method_scores_an_empty_stratum_as_an_empty_run(method) -> None:
    assert method.score((), CONTEXT).scores == ()


# Registry


def test_registry_lists_every_score_method() -> None:
    assert SCORE_METHODS.method_ids == (
        "constructed-score",
        "foundation",
        "hidden-gem-score",
        "max-ratio",
        "signature-score",
    )
    assert "max-ratio" in SCORE_METHODS
    assert "unknown" not in SCORE_METHODS
    assert isinstance(SCORE_METHODS.get("foundation"), FoundationMethod)


def test_registry_lookup_names_the_available_methods() -> None:
    available = "constructed-score, foundation, hidden-gem-score, max-ratio, signature-score"
    with pytest.raises(KeyError, match=f"available: {available}"):
        SCORE_METHODS.get("power-ranking")


def test_registry_rejects_duplicate_method_ids() -> None:
    other_measure = MaxRatioMethod(MaxRatioConfig(measure="event_count"))

    with pytest.raises(ValueError, match="duplicate score method 'max-ratio'"):
        ScoreMethodRegistry((MaxRatioMethod(), other_measure))


def test_registry_rejects_blank_method_ids() -> None:
    with pytest.raises(ValueError, match="method_id cannot be blank"):
        ScoreMethodRegistry((SimpleNamespace(method_id=" "),))


# Shared result types


def test_scoring_input_requires_a_card_identity() -> None:
    with pytest.raises(ValueError, match="card_id cannot be blank"):
        ScoringInput(" ", CardFeatures.empty())


def test_card_score_values_cannot_be_changed_after_scoring() -> None:
    score = CardScore("card-a", {"max_ratio": 50.0})

    with pytest.raises(TypeError):
        score.values["max_ratio"] = 100.0  # type: ignore[index]


def test_a_run_cannot_score_the_same_card_twice() -> None:
    with pytest.raises(ValueError, match="same card twice"):
        build_run(
            MaxRatioMethod(),
            CONTEXT,
            (CardScore("card-a", {"max_ratio": 1.0}), CardScore("card-a", {"max_ratio": 2.0})),
        )


def test_a_method_must_return_exactly_its_declared_outputs() -> None:
    with pytest.raises(ValueError, match="must return outputs"):
        build_run(MaxRatioMethod(), CONTEXT, (CardScore("card-a", {"ratio": 1.0}),))


# Foundation model


def test_foundation_method_returns_score_card_for_every_card() -> None:
    run = FoundationMethod().score(STRATUM, CONTEXT)

    for card, score in zip(STRATUM, run.scores, strict=True):
        breakdown = score_card(card.features, CONTEXT)
        assert score.values == {name: getattr(breakdown, name) for name in FoundationMethod.outputs}


def test_foundation_identity_comes_from_its_score_config() -> None:
    reweighted = ScoreConfig(
        version="foundation-v3",
        staple_incidence=0.34,
        staple_deck_family_breadth=0.26,
    )

    assert FoundationMethod().version == DEFAULT_CONFIG.version
    assert FoundationMethod().config_hash == DEFAULT_CONFIG.fingerprint
    assert FoundationMethod(reweighted).version == "foundation-v3"
    assert FoundationMethod(reweighted).config_hash != DEFAULT_CONFIG.fingerprint


# Max-ratio


def test_max_ratio_scores_the_leader_100_and_others_by_their_ratio_to_it() -> None:
    run = MaxRatioMethod().score(
        (counted("leader", decks=20), counted("close", decks=19), counted("third", decks=5)),
        CONTEXT,
    )

    assert ratios(run) == {"leader": 100.0, "close": 95.0, "third": 25.0}


def test_max_ratio_records_the_count_and_maximum_behind_each_score() -> None:
    run = MaxRatioMethod().score((counted("leader", decks=20), counted("close", decks=19)), CONTEXT)

    assert run.scores[1].inputs == {"count": 19, "max_count": 20}


def test_max_ratio_ties_at_the_maximum_all_score_100() -> None:
    run = MaxRatioMethod().score((counted("a", decks=8), counted("b", decks=8)), CONTEXT)

    assert ratios(run) == {"a": 100.0, "b": 100.0}


def test_max_ratio_scores_an_observed_zero_as_zero() -> None:
    run = MaxRatioMethod().score((counted("played", decks=4), counted("unplayed")), CONTEXT)

    assert ratios(run)["unplayed"] == 0.0


def test_max_ratio_is_unknown_when_no_scored_card_has_any_count() -> None:
    run = MaxRatioMethod().score((counted("a"), counted("b")), CONTEXT)

    assert ratios(run) == {"a": None, "b": None}
    assert run.scores[0].inputs == {"count": 0, "max_count": 0}


def test_max_ratio_rounds_to_one_decimal_like_other_scores() -> None:
    run = MaxRatioMethod().score((counted("a", decks=3), counted("b", decks=1)), CONTEXT)

    assert ratios(run)["b"] == 33.3


def test_max_ratio_compares_the_configured_measure() -> None:
    by_events = MaxRatioMethod(MaxRatioConfig(measure="event_count"))
    run = by_events.score(
        (counted("many-decks", decks=40, events=2), counted("many-events", decks=10, events=8)),
        CONTEXT,
    )

    assert ratios(run) == {"many-decks": 25.0, "many-events": 100.0}


def test_max_ratio_identity_changes_with_its_configuration() -> None:
    default = MaxRatioMethod()
    by_events = MaxRatioMethod(MaxRatioConfig(measure="event_count"))

    assert default.version == "max-ratio-v1"
    assert default.config_hash != by_events.config_hash


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"measure": "games"}, "measure must be one of"),
        ({"version": " "}, "version cannot be blank"),
    ],
)
def test_max_ratio_config_rejects_unsupported_settings(arguments, message) -> None:
    with pytest.raises(ValueError, match=message):
        MaxRatioConfig(**arguments)
