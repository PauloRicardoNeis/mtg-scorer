from dataclasses import replace

import pytest

from mtg_scorer import (
    CardFeatures,
    FeatureObservation,
    ScoreConfig,
    ScoreContext,
    score_card,
)

CONTEXT = ScoreContext(
    dataset_snapshot_id="fixture-2026-08-28",
    feature_pipeline_version="test-features-v1",
)


def observed(value: float, support: int = 1) -> FeatureObservation:
    return FeatureObservation.known(value, support=support)


def test_obscurity_alone_does_not_create_a_buildaround_signal() -> None:
    scores = score_card(CardFeatures.empty(), CONTEXT)

    assert scores.staple == 0.0
    assert scores.buildaround_signal == 0.0
    assert scores.evidence == 0.0
    assert scores.distinctiveness_delta == 0.0
    assert scores.staple_feature_coverage == 0.0
    assert scores.buildaround_feature_coverage == 0.0


def test_one_coherent_success_can_be_high_signal_but_low_evidence() -> None:
    features = CardFeatures(
        incidence=observed(0.02),
        deck_family_breadth=observed(0.03),
        format_era_breadth=observed(0.05),
        competitive_proof=observed(0.90),
        commitment=observed(1.0),
        specificity=observed(0.95),
        package_coherence=observed(0.95),
        recurrence=observed(0.15),
        choice_freedom=observed(0.85),
        coverage_strength=observed(0.5),
        deck_count=1,
        event_count=1,
    )

    scores = score_card(features, CONTEXT)

    assert scores.buildaround_signal > 80
    assert scores.staple < 30
    assert scores.distinctiveness_delta > 50
    assert scores.evidence < 30


def test_broad_repeated_usage_produces_a_high_staple_score() -> None:
    features = CardFeatures(
        incidence=observed(0.95, 5_000),
        deck_family_breadth=observed(0.95, 5_000),
        format_era_breadth=observed(0.9, 500),
        competitive_proof=observed(0.85, 20_000),
        commitment=observed(0.85, 5_000),
        specificity=observed(0.1, 5_000),
        package_coherence=observed(0.1, 5_000),
        recurrence=observed(1.0, 500),
        choice_freedom=observed(0.9, 500),
        coverage_strength=observed(0.95, 500),
        deck_count=5_000,
        event_count=500,
        full_field_match_count=20_000,
    )

    scores = score_card(features, CONTEXT)

    assert scores.staple > 90
    assert scores.staple > scores.buildaround_signal
    assert scores.evidence > 95
    assert scores.distinctiveness_delta < 0


def test_unknown_feature_is_not_interpreted_as_zero() -> None:
    without_competitive_data = CardFeatures(
        incidence=observed(0.8),
        commitment=observed(0.8),
        deck_count=10,
    )
    measured_zero = replace(
        without_competitive_data,
        competitive_proof=observed(0.0),
    )

    unknown_scores = score_card(without_competitive_data, CONTEXT)
    zero_scores = score_card(measured_zero, CONTEXT)

    assert unknown_scores.staple == 80.0
    assert zero_scores.staple < unknown_scores.staple
    assert unknown_scores.staple_feature_coverage < zero_scores.staple_feature_coverage


def test_high_buildaround_features_require_observed_deck_evidence() -> None:
    features = CardFeatures(
        specificity=observed(1.0),
        package_coherence=observed(1.0),
        commitment=observed(1.0),
        competitive_proof=observed(1.0),
        recurrence=observed(1.0),
        choice_freedom=observed(1.0),
        deck_count=0,
    )

    assert score_card(features, CONTEXT).buildaround_signal == 0.0


def test_feature_values_must_be_normalized() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        observed(1.01)


def test_score_identity_includes_data_features_and_config_hash() -> None:
    default = score_card(CardFeatures.empty(), CONTEXT)
    changed_config = replace(
        ScoreConfig(),
        staple_incidence=0.34,
        staple_deck_family_breadth=0.26,
    )
    changed = score_card(CardFeatures.empty(), CONTEXT, changed_config)

    assert default.dataset_snapshot_id == CONTEXT.dataset_snapshot_id
    assert default.feature_pipeline_version == CONTEXT.feature_pipeline_version
    assert default.model_config_hash != changed.model_config_hash


def test_distinctiveness_is_exactly_buildaround_minus_staple() -> None:
    scores = score_card(
        CardFeatures(
            incidence=observed(0.2),
            deck_family_breadth=observed(0.1),
            format_era_breadth=observed(0.1),
            competitive_proof=observed(0.7),
            commitment=observed(0.8),
            specificity=observed(0.9),
            package_coherence=observed(0.9),
            recurrence=observed(0.4),
            choice_freedom=observed(0.7),
            coverage_strength=observed(0.6),
            deck_count=4,
            event_count=2,
        ),
        CONTEXT,
    )

    assert scores.distinctiveness_delta == pytest.approx(
        scores.buildaround_signal - scores.staple,
        abs=0.05,
    )
