"""Replaceable score models over normalized historical features.

The formulas in this module are deliberately provisional. Their job in the
foundation release is to establish invariants and interfaces, not to canonize a
particular weighting scheme.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

from .domain import CardFeatures


def _validate_weight_group(name: str, weights: tuple[float, ...]) -> None:
    if any(weight < 0 for weight in weights):
        raise ValueError(f"{name} weights cannot be negative")
    if abs(sum(weights) - 1.0) > 1e-9:
        raise ValueError(f"{name} weights must sum to 1.0; got {sum(weights)}")


@dataclass(frozen=True, slots=True)
class ScoreConfig:
    """Versioned weights for one interpretation of the historical evidence."""

    version: str = "foundation-v1"

    # Staple score: breadth and incidence are intentionally dominant.
    staple_incidence: float = 0.35
    staple_archetype_breadth: float = 0.25
    staple_format_era_breadth: float = 0.15
    staple_competitive_proof: float = 0.20
    staple_commitment: float = 0.05

    # Engine score: package/specificity dominate and repetition saturates upstream.
    engine_specificity: float = 0.25
    engine_package_coherence: float = 0.25
    engine_commitment: float = 0.15
    engine_competitive_proof: float = 0.20
    engine_repeat_evidence: float = 0.10
    engine_choice_freedom: float = 0.05

    # Evidence score: sample volume and coverage quality are separate from the estimate.
    evidence_decks: float = 0.35
    evidence_events: float = 0.30
    evidence_matches: float = 0.20
    evidence_coverage: float = 0.15

    def __post_init__(self) -> None:
        _validate_weight_group(
            "staple",
            (
                self.staple_incidence,
                self.staple_archetype_breadth,
                self.staple_format_era_breadth,
                self.staple_competitive_proof,
                self.staple_commitment,
            ),
        )
        _validate_weight_group(
            "engine",
            (
                self.engine_specificity,
                self.engine_package_coherence,
                self.engine_commitment,
                self.engine_competitive_proof,
                self.engine_repeat_evidence,
                self.engine_choice_freedom,
            ),
        )
        _validate_weight_group(
            "evidence",
            (
                self.evidence_decks,
                self.evidence_events,
                self.evidence_matches,
                self.evidence_coverage,
            ),
        )


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """Human-facing scores on a 0-100 scale, except uniqueness (-100 to 100)."""

    model_version: str
    staple: float
    engine: float
    evidence: float
    uniqueness: float


DEFAULT_CONFIG = ScoreConfig()


def score_card(
    features: CardFeatures,
    config: ScoreConfig = DEFAULT_CONFIG,
) -> ScoreBreakdown:
    """Score a feature vector without mutating or interpreting source data.

    A card with no observed decks is hard-gated to zero Engine score. This prevents
    obscurity alone from masquerading as strategic uniqueness. Once at least one
    observation exists, sparse evidence is reflected by the independent Evidence
    score instead of automatically crushing the Engine estimate.
    """

    staple = 100.0 * (
        config.staple_incidence * features.incidence
        + config.staple_archetype_breadth * features.archetype_breadth
        + config.staple_format_era_breadth * features.format_era_breadth
        + config.staple_competitive_proof * features.competitive_proof
        + config.staple_commitment * features.commitment
    )

    if features.deck_count == 0:
        engine = 0.0
    else:
        engine = 100.0 * (
            config.engine_specificity * features.specificity
            + config.engine_package_coherence * features.package_coherence
            + config.engine_commitment * features.commitment
            + config.engine_competitive_proof * features.competitive_proof
            + config.engine_repeat_evidence * features.repeat_evidence
            + config.engine_choice_freedom * features.choice_freedom
        )

    evidence = 100.0 * (
        config.evidence_decks * _saturating_evidence(features.deck_count, scale=8.0)
        + config.evidence_events * _saturating_evidence(features.event_count, scale=4.0)
        + config.evidence_matches * _saturating_evidence(features.full_field_matches, scale=40.0)
        + config.evidence_coverage * features.coverage_strength
    )

    staple = _round_score(staple)
    engine = _round_score(engine)
    evidence = _round_score(evidence)
    uniqueness = round(engine - staple, 1)

    return ScoreBreakdown(
        model_version=config.version,
        staple=staple,
        engine=engine,
        evidence=evidence,
        uniqueness=uniqueness,
    )


def _saturating_evidence(count: int, *, scale: float) -> float:
    """Map count to [0, 1) with large gains early and diminishing returns later."""

    if count <= 0:
        return 0.0
    return 1.0 - exp(-count / scale)


def _round_score(value: float) -> float:
    return round(min(100.0, max(0.0, value)), 1)
