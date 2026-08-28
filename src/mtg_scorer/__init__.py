"""Historical MTG card analytics."""

from .domain import (
    CardPrinting,
    CoverageDimension,
    CoverageProfile,
    CoverageScope,
    DeckCard,
    DeckEntry,
    Match,
    MatchParticipant,
    MatchResult,
    OracleCard,
    Provenance,
    Standing,
    Tournament,
)
from .features import CardFeatures, FeatureObservation
from .publication import (
    PublishedCard,
    PublishedPrinting,
    build_catalog,
    build_demonstration_catalog,
    write_catalog,
)
from .scoring import ScoreBreakdown, ScoreConfig, ScoreContext, score_card

__all__ = [
    "CardFeatures",
    "CardPrinting",
    "CoverageDimension",
    "CoverageProfile",
    "CoverageScope",
    "DeckCard",
    "DeckEntry",
    "FeatureObservation",
    "Match",
    "MatchParticipant",
    "MatchResult",
    "OracleCard",
    "Provenance",
    "PublishedCard",
    "PublishedPrinting",
    "ScoreBreakdown",
    "ScoreConfig",
    "ScoreContext",
    "Standing",
    "Tournament",
    "build_catalog",
    "build_demonstration_catalog",
    "score_card",
    "write_catalog",
]
