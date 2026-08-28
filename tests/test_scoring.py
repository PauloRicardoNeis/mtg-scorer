import pytest

from mtg_scorer import CardFeatures, score_card


def make_features(**overrides: float | int) -> CardFeatures:
    values: dict[str, float | int] = {
        "incidence": 0.0,
        "archetype_breadth": 0.0,
        "format_era_breadth": 0.0,
        "competitive_proof": 0.0,
        "commitment": 0.0,
        "specificity": 0.0,
        "package_coherence": 0.0,
        "repeat_evidence": 0.0,
        "choice_freedom": 0.0,
        "coverage_strength": 0.0,
        "deck_count": 0,
        "event_count": 0,
        "full_field_matches": 0,
    }
    values.update(overrides)
    return CardFeatures(**values)


def test_obscurity_alone_does_not_create_an_engine() -> None:
    scores = score_card(CardFeatures.empty())

    assert scores.staple == 0.0
    assert scores.engine == 0.0
    assert scores.evidence == 0.0
    assert scores.uniqueness == 0.0


def test_one_coherent_success_can_be_high_engine_but_low_evidence() -> None:
    features = make_features(
        incidence=0.02,
        archetype_breadth=0.03,
        format_era_breadth=0.05,
        competitive_proof=0.90,
        commitment=1.0,
        specificity=0.95,
        package_coherence=0.95,
        repeat_evidence=0.15,
        choice_freedom=0.85,
        coverage_strength=0.5,
        deck_count=1,
        event_count=1,
    )

    scores = score_card(features)

    assert scores.engine > 80
    assert scores.staple < 30
    assert scores.uniqueness > 50
    assert scores.evidence < 30


def test_broad_repeated_usage_produces_a_high_staple_score() -> None:
    features = make_features(
        incidence=0.95,
        archetype_breadth=0.95,
        format_era_breadth=0.9,
        competitive_proof=0.85,
        commitment=0.85,
        specificity=0.1,
        package_coherence=0.1,
        repeat_evidence=1.0,
        choice_freedom=0.9,
        coverage_strength=0.95,
        deck_count=5_000,
        event_count=500,
        full_field_matches=20_000,
    )

    scores = score_card(features)

    assert scores.staple > 90
    assert scores.staple > scores.engine
    assert scores.evidence > 95
    assert scores.uniqueness < 0


def test_high_engine_requires_observed_deck_evidence() -> None:
    features = make_features(
        specificity=1.0,
        package_coherence=1.0,
        commitment=1.0,
        competitive_proof=1.0,
        repeat_evidence=1.0,
        choice_freedom=1.0,
        deck_count=0,
    )

    assert score_card(features).engine == 0.0


def test_feature_values_must_be_normalized() -> None:
    with pytest.raises(ValueError, match="incidence"):
        make_features(incidence=1.01)


def test_uniqueness_is_exactly_engine_minus_staple_after_normalization() -> None:
    scores = score_card(
        make_features(
            incidence=0.2,
            archetype_breadth=0.1,
            format_era_breadth=0.1,
            competitive_proof=0.7,
            commitment=0.8,
            specificity=0.9,
            package_coherence=0.9,
            repeat_evidence=0.4,
            choice_freedom=0.7,
            coverage_strength=0.6,
            deck_count=4,
            event_count=2,
        )
    )

    assert scores.uniqueness == pytest.approx(scores.engine - scores.staple, abs=0.05)
