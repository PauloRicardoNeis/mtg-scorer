"""Versioned score-catalog publication for product consumers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from json import dumps
from pathlib import Path
from typing import Any

from .features import CardFeatures, FeatureObservation
from .scoring import ScoreBreakdown, ScoreContext, score_card

CATALOG_CONTRACT_VERSION = "card-catalog-v1"
DEMONSTRATION_CATALOG_KIND = "DEMONSTRATION"
DEMONSTRATION_PUBLISHED_AT = datetime(2026, 8, 28, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class PublishedPrinting:
    """Printing metadata used by Forge-oriented product filters."""

    set_code: str
    rarity: str
    released_at: str


@dataclass(frozen=True, slots=True)
class PublishedCard:
    """One scored Oracle card and its human-facing explanation."""

    oracle_id: str
    name: str
    colors: tuple[str, ...]
    printings: tuple[PublishedPrinting, ...]
    scores: ScoreBreakdown
    reasons: tuple[str, ...]


def build_catalog(
    cards: tuple[PublishedCard, ...],
    *,
    catalog_kind: str,
    published_at: datetime,
) -> dict[str, Any]:
    """Build the stable JSON boundary consumed by the Java product API."""

    if published_at.tzinfo is None or published_at.utcoffset() is None:
        raise ValueError("published_at must be timezone-aware")
    if not cards:
        raise ValueError("a published catalog must contain at least one card")

    oracle_ids = tuple(card.oracle_id for card in cards)
    if len(set(oracle_ids)) != len(oracle_ids):
        raise ValueError("published catalog oracle IDs must be unique")

    identity = _score_identity(cards[0].scores)
    if any(_score_identity(card.scores) != identity for card in cards[1:]):
        raise ValueError("every card in a catalog must share one score identity")

    return {
        "contractVersion": CATALOG_CONTRACT_VERSION,
        "catalogKind": catalog_kind,
        "snapshot": {
            "datasetSnapshotId": identity[0],
            "featurePipelineVersion": identity[1],
            "scoreModelVersion": identity[2],
            "scoreConfigHash": identity[3],
            "publishedAt": published_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        },
        "cards": [_serialize_card(card) for card in cards],
    }


def write_catalog(catalog: dict[str, Any], output_file: Path) -> None:
    """Atomically replace a product catalog with canonical JSON."""

    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = output_file.with_suffix(f"{output_file.suffix}.tmp")
    temporary_file.write_text(
        dumps(catalog, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_file.replace(output_file)


def build_demonstration_catalog(*, published_at: datetime | None = None) -> dict[str, Any]:
    """Produce synthetic cards that exercise the product contract.

    These observations are deliberately invented and the catalog is marked as a
    demonstration. They validate the product boundary without posing as empirical
    tournament evidence.
    """

    context = ScoreContext(
        dataset_snapshot_id="demo-synthetic-v1",
        feature_pipeline_version="demo-features-v1",
    )
    cards = (
        _published_card(
            oracle_id="oracle-demo-bolt",
            name="Example Bolt",
            colors=("R",),
            printings=(
                PublishedPrinting("old", "common", "2020-01-01"),
                PublishedPrinting("new", "uncommon", "2024-01-01"),
            ),
            features=CardFeatures(
                incidence=_observed(0.92),
                deck_family_breadth=_observed(0.88),
                format_era_breadth=_observed(0.85),
                competitive_proof=_observed(0.90),
                commitment=_observed(0.70),
                specificity=_observed(0.12),
                package_coherence=_observed(0.20),
                recurrence=_observed(0.95),
                choice_freedom=_observed(0.95),
                coverage_strength=_observed(0.92),
                deck_count=400,
                event_count=80,
                full_field_match_count=1_200,
            ),
            context=context,
        ),
        _published_card(
            oracle_id="oracle-demo-engine",
            name="Example Engine",
            colors=(),
            printings=(PublishedPrinting("eng", "rare", "2023-06-01"),),
            features=CardFeatures(
                incidence=_observed(0.04),
                deck_family_breadth=_observed(0.08),
                format_era_breadth=_observed(0.15),
                competitive_proof=_observed(0.75),
                commitment=_observed(0.95),
                specificity=_observed(0.95),
                package_coherence=_observed(0.90),
                recurrence=_observed(0.35),
                choice_freedom=_observed(0.80),
                coverage_strength=_observed(0.70),
                deck_count=4,
                event_count=3,
                full_field_match_count=12,
            ),
            context=context,
        ),
        _published_card(
            oracle_id="oracle-demo-recursive-threat",
            name="Example Recursive Threat",
            colors=("B",),
            printings=(PublishedPrinting("rec", "uncommon", "2021-10-08"),),
            features=CardFeatures(
                incidence=_observed(0.30),
                deck_family_breadth=_observed(0.28),
                format_era_breadth=_observed(0.45),
                competitive_proof=_observed(0.72),
                commitment=_observed(0.85),
                specificity=_observed(0.68),
                package_coherence=_observed(0.76),
                recurrence=_observed(0.62),
                choice_freedom=_observed(0.70),
                coverage_strength=_observed(0.82),
                deck_count=42,
                event_count=18,
                full_field_match_count=240,
            ),
            context=context,
        ),
    )
    return build_catalog(
        cards,
        catalog_kind=DEMONSTRATION_CATALOG_KIND,
        published_at=published_at or DEMONSTRATION_PUBLISHED_AT,
    )


def _published_card(
    *,
    oracle_id: str,
    name: str,
    colors: tuple[str, ...],
    printings: tuple[PublishedPrinting, ...],
    features: CardFeatures,
    context: ScoreContext,
) -> PublishedCard:
    return PublishedCard(
        oracle_id=oracle_id,
        name=name,
        colors=colors,
        printings=printings,
        scores=score_card(features, context),
        reasons=_explain(features),
    )


def _observed(value: float) -> FeatureObservation:
    return FeatureObservation.known(value, support=1)


def _explain(features: CardFeatures) -> tuple[str, ...]:
    reasons: list[str] = []
    if (features.incidence.value or 0.0) >= 0.70:
        reasons.append("Broad repeated incidence raises the Staple estimate.")
    if (features.specificity.value or 0.0) >= 0.60:
        reasons.append("Strategy concentration raises the Build-around estimate.")
    if (features.package_coherence.value or 0.0) >= 0.60:
        reasons.append("A coherent supporting package strengthens strategic specificity.")
    if (features.recurrence.value or 0.0) >= 0.60:
        reasons.append("Recurrence across bounded contexts strengthens the signal.")
    if not reasons:
        reasons.append("The score combines the available normalized observations.")
    return tuple(reasons)


def _score_identity(scores: ScoreBreakdown) -> tuple[str, str, str, str]:
    return (
        scores.dataset_snapshot_id,
        scores.feature_pipeline_version,
        scores.model_version,
        scores.model_config_hash,
    )


def _serialize_card(card: PublishedCard) -> dict[str, Any]:
    return {
        "oracleId": card.oracle_id,
        "name": card.name,
        "colors": list(card.colors),
        "printings": [
            {
                "setCode": printing.set_code,
                "rarity": printing.rarity,
                "releasedAt": printing.released_at,
            }
            for printing in card.printings
        ],
        "scores": {
            "staple": card.scores.staple,
            "buildaroundSignal": card.scores.buildaround_signal,
            "evidence": card.scores.evidence,
            "distinctivenessDelta": card.scores.distinctiveness_delta,
            "stapleFeatureCoverage": card.scores.staple_feature_coverage,
            "buildaroundFeatureCoverage": card.scores.buildaround_feature_coverage,
        },
        "reasons": list(card.reasons),
    }
