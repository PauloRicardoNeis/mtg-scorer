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


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        pytest.param({"value": -0.01}, "between 0 and 1", id="below-zero"),
        pytest.param({"value": float("nan")}, "between 0 and 1", id="nan"),
        pytest.param({"value": 0.5, "support": -1}, "support cannot be negative", id="support"),
        pytest.param(
            {"value": 0.5, "opportunity_count": -1},
            "opportunity_count cannot be negative",
            id="opportunities",
        ),
        pytest.param(
            {"value": 0.5, "support": 3, "opportunity_count": 2},
            "support cannot exceed opportunity_count",
            id="support-exceeds-opportunities",
        ),
    ],
)
def test_feature_observations_reject_impossible_measurements(arguments, message) -> None:
    with pytest.raises(ValueError, match=message):
        FeatureObservation(**arguments)


def test_feature_bounds_and_full_support_are_valid_measurements() -> None:
    assert FeatureObservation.known(0.0, support=2, opportunity_count=2).is_known
    assert FeatureObservation.known(1.0).is_known
    assert not FeatureObservation.unknown().is_known


@pytest.mark.parametrize("count", ["deck_count", "event_count", "full_field_match_count"])
def test_card_feature_population_counts_cannot_be_negative(count) -> None:
    with pytest.raises(ValueError, match=f"{count} cannot be negative"):
        CardFeatures(**{count: -1})


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        pytest.param(
            {"staple_incidence": 0.45, "staple_commitment": -0.05},
            "staple weights cannot be negative",
            id="negative-staple",
        ),
        pytest.param(
            {"buildaround_choice_freedom": 0.10},
            "buildaround weights must sum to 1.0",
            id="buildaround-overweight",
        ),
        pytest.param(
            {"evidence_feature_availability": 0.0},
            "evidence weights must sum to 1.0",
            id="evidence-underweight",
        ),
        pytest.param({"version": " "}, "version cannot be blank", id="blank-version"),
    ],
)
def test_score_config_rejects_weights_outside_a_convex_combination(weights, message) -> None:
    with pytest.raises(ValueError, match=message):
        replace(ScoreConfig(), **weights)


@pytest.mark.parametrize("weight", [float("nan"), float("inf"), float("-inf")])
def test_score_config_rejects_non_finite_weights(weight) -> None:
    with pytest.raises(ValueError, match="staple weights must be finite"):
        replace(ScoreConfig(), staple_incidence=weight)


@pytest.mark.parametrize("field_name", ["dataset_snapshot_id", "feature_pipeline_version"])
def test_score_context_requires_reproducible_identities(field_name) -> None:
    with pytest.raises(ValueError, match=f"{field_name} cannot be blank"):
        replace(CONTEXT, **{field_name: " "})


def test_feature_coverage_reports_the_observable_share_of_each_model() -> None:
    scores = score_card(
        CardFeatures(
            incidence=observed(0.5),
            competitive_proof=observed(1.0),
            specificity=observed(0.2),
            deck_count=1,
        ),
        CONTEXT,
    )

    assert scores.staple_feature_coverage == pytest.approx(100 * (0.35 + 0.20))
    assert scores.buildaround_feature_coverage == pytest.approx(100 * (0.25 + 0.20))
    assert scores.staple == pytest.approx(100 * (0.5 * 0.35 + 1.0 * 0.20) / 0.55, abs=0.05)


@pytest.mark.parametrize(
    ("population", "weight"),
    [
        ("deck_count", "evidence_decks"),
        ("event_count", "evidence_events"),
        ("full_field_match_count", "evidence_matches"),
    ],
)
def test_evidence_grows_with_each_population_and_saturates_at_its_weight(
    population, weight
) -> None:
    evidence = [
        score_card(CardFeatures(**{population: count}), CONTEXT).evidence
        for count in (0, 1, 10, 1_000_000)
    ]

    assert evidence == sorted(set(evidence))
    assert evidence[-1] == pytest.approx(100 * getattr(ScoreConfig(), weight), abs=0.05)
