"""Replaceable score models over missing-aware historical features."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from json import dumps
from math import exp

from .features import CardFeatures, FeatureObservation


def _validate_weight_group(name: str, weights: tuple[float, ...]) -> None:
    if any(weight < 0 for weight in weights):
        raise ValueError(f"{name} weights cannot be negative")
    if abs(sum(weights) - 1.0) > 1e-9:
        raise ValueError(f"{name} weights must sum to 1.0; got {sum(weights)}")


@dataclass(frozen=True, slots=True)
class ScoreContext:
    """Data and feature identities required to reproduce a score."""

    dataset_snapshot_id: str
    feature_pipeline_version: str

    def __post_init__(self) -> None:
        for field_name in ("dataset_snapshot_id", "feature_pipeline_version"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be blank")


@dataclass(frozen=True, slots=True)
class ScoreConfig:
    """Versioned weights for one interpretation of historical evidence."""

    version: str = "foundation-v2"

    staple_incidence: float = 0.35
    staple_deck_family_breadth: float = 0.25
    staple_format_era_breadth: float = 0.15
    staple_competitive_proof: float = 0.20
    staple_commitment: float = 0.05

    buildaround_specificity: float = 0.25
    buildaround_package_coherence: float = 0.25
    buildaround_commitment: float = 0.15
    buildaround_competitive_proof: float = 0.20
    buildaround_recurrence: float = 0.10
    buildaround_choice_freedom: float = 0.05

    evidence_decks: float = 0.30
    evidence_events: float = 0.25
    evidence_matches: float = 0.20
    evidence_source_coverage: float = 0.15
    evidence_feature_availability: float = 0.10

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("version cannot be blank")
        _validate_weight_group(
            "staple",
            (
                self.staple_incidence,
                self.staple_deck_family_breadth,
                self.staple_format_era_breadth,
                self.staple_competitive_proof,
                self.staple_commitment,
            ),
        )
        _validate_weight_group(
            "buildaround",
            (
                self.buildaround_specificity,
                self.buildaround_package_coherence,
                self.buildaround_commitment,
                self.buildaround_competitive_proof,
                self.buildaround_recurrence,
                self.buildaround_choice_freedom,
            ),
        )
        _validate_weight_group(
            "evidence",
            (
                self.evidence_decks,
                self.evidence_events,
                self.evidence_matches,
                self.evidence_source_coverage,
                self.evidence_feature_availability,
            ),
        )

    @property
    def fingerprint(self) -> str:
        """Hash the complete configuration so a reused version label cannot lie."""

        payload = dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """Human-facing estimates plus their complete computational identity."""

    model_version: str
    model_config_hash: str
    dataset_snapshot_id: str
    feature_pipeline_version: str
    staple: float
    buildaround_signal: float
    evidence: float
    distinctiveness_delta: float
    staple_feature_coverage: float
    buildaround_feature_coverage: float


DEFAULT_CONFIG = ScoreConfig()


def score_card(
    features: CardFeatures,
    context: ScoreContext,
    config: ScoreConfig = DEFAULT_CONFIG,
) -> ScoreBreakdown:
    """Score normalized features without interpreting unavailable data as zero.

    Known features are reweighted within their score group. The returned feature
    coverage records how much of the configured model was actually observable.
    A build-around score is a strategy-specificity signal, not a causal assertion
    that the card alone generated its associated deck.
    """

    staple, staple_coverage = _weighted_estimate(
        (
            (features.incidence, config.staple_incidence),
            (features.deck_family_breadth, config.staple_deck_family_breadth),
            (features.format_era_breadth, config.staple_format_era_breadth),
            (features.competitive_proof, config.staple_competitive_proof),
            (features.commitment, config.staple_commitment),
        )
    )

    if features.deck_count == 0:
        buildaround = 0.0
        buildaround_coverage = 0.0
    else:
        buildaround, buildaround_coverage = _weighted_estimate(
            (
                (features.specificity, config.buildaround_specificity),
                (features.package_coherence, config.buildaround_package_coherence),
                (features.commitment, config.buildaround_commitment),
                (features.competitive_proof, config.buildaround_competitive_proof),
                (features.recurrence, config.buildaround_recurrence),
                (features.choice_freedom, config.buildaround_choice_freedom),
            )
        )

    feature_availability = (staple_coverage + buildaround_coverage) / 2.0
    source_coverage = features.coverage_strength.value or 0.0
    evidence = 100.0 * (
        config.evidence_decks * _saturating_evidence(features.deck_count, scale=8.0)
        + config.evidence_events * _saturating_evidence(features.event_count, scale=4.0)
        + config.evidence_matches
        * _saturating_evidence(features.full_field_match_count, scale=40.0)
        + config.evidence_source_coverage * source_coverage
        + config.evidence_feature_availability * feature_availability
    )

    staple = _round_score(staple)
    buildaround = _round_score(buildaround)
    evidence = _round_score(evidence)

    return ScoreBreakdown(
        model_version=config.version,
        model_config_hash=config.fingerprint,
        dataset_snapshot_id=context.dataset_snapshot_id,
        feature_pipeline_version=context.feature_pipeline_version,
        staple=staple,
        buildaround_signal=buildaround,
        evidence=evidence,
        distinctiveness_delta=round(buildaround - staple, 1),
        staple_feature_coverage=round(100.0 * staple_coverage, 1),
        buildaround_feature_coverage=round(100.0 * buildaround_coverage, 1),
    )


def _weighted_estimate(
    observations: tuple[tuple[FeatureObservation, float], ...],
) -> tuple[float, float]:
    known = tuple(
        (observation.value, weight) for observation, weight in observations if observation.is_known
    )
    covered_weight = sum(weight for _, weight in known)
    if covered_weight == 0.0:
        return 0.0, 0.0
    estimate = sum(value * weight for value, weight in known if value is not None) / covered_weight
    return 100.0 * estimate, covered_weight


def _saturating_evidence(count: int, *, scale: float) -> float:
    if count <= 0:
        return 0.0
    return 1.0 - exp(-count / scale)


def _round_score(value: float) -> float:
    return round(min(100.0, max(0.0, value)), 1)
