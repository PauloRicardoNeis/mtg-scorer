"""The contract every replaceable score method implements."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from json import dumps
from types import MappingProxyType
from typing import Any, ClassVar, Protocol

from ..features import CardFeatures


@dataclass(frozen=True, slots=True)
class ScoreContext:
    """Data and feature identities required to reproduce a score."""

    dataset_snapshot_id: str
    feature_pipeline_version: str

    def __post_init__(self) -> None:
        for field_name in ("dataset_snapshot_id", "feature_pipeline_version"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be blank")


def config_fingerprint(config: Any) -> str:
    """Hash a complete dataclass configuration so a reused version label cannot lie."""

    payload = dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ScoringInput:
    """One eligible card of a stratum and the features measured for it.

    The cards passed to a method together form the population it scores. A card left
    out has no score at all; it is never scored as zero.
    """

    card_id: str
    features: CardFeatures

    def __post_init__(self) -> None:
        if not self.card_id.strip():
            raise ValueError("card_id cannot be blank")


@dataclass(frozen=True, slots=True)
class CardScore:
    """One card's named outputs from one method, plus the inputs that explain them.

    An output of ``None`` means the method could not score the card, not zero.
    """

    card_id: str
    values: Mapping[str, float | None]
    inputs: Mapping[str, float | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))


@dataclass(frozen=True, slots=True)
class ScoreRun:
    """Every card one method scored in one stratum, with its complete identity."""

    method_id: str
    method_version: str
    method_config_hash: str
    dataset_snapshot_id: str
    feature_pipeline_version: str
    scores: tuple[CardScore, ...]

    def __post_init__(self) -> None:
        card_ids = [score.card_id for score in self.scores]
        if len(set(card_ids)) != len(card_ids):
            raise ValueError("a score run cannot score the same card twice")


class ScoreMethod(Protocol):
    """A versioned way to turn one stratum's features into scores.

    ``version`` and ``config_hash`` come from the method's configuration, so a changed
    formula setting always produces a new identity. Scoring must be deterministic.
    The identity and outputs are fixed per class; only the configuration varies.
    """

    method_id: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str]
    outputs: ClassVar[tuple[str, ...]]

    @property
    def version(self) -> str: ...

    @property
    def config_hash(self) -> str: ...

    def score(self, cards: Sequence[ScoringInput], context: ScoreContext) -> ScoreRun: ...


def percentiles(values: Mapping[str, float]) -> dict[str, float]:
    """Mid-rank percentiles in (0, 1); ties share their average rank."""

    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    result: dict[str, float] = {}
    start = 0
    while start < len(ordered):
        end = start
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[start][1]:
            end += 1
        rank = (start + end) / 2 + 0.5
        for card_id, _ in ordered[start : end + 1]:
            result[card_id] = rank / len(ordered)
        start = end + 1
    return result


def build_run(
    method: ScoreMethod,
    context: ScoreContext,
    scores: Iterable[CardScore],
) -> ScoreRun:
    """Attach a method's identity to its scores, checking each has exactly its outputs."""

    scores = tuple(scores)
    expected = set(method.outputs)
    for score in scores:
        if set(score.values) != expected:
            raise ValueError(
                f"{method.method_id} must return outputs {sorted(expected)} for "
                f"{score.card_id}; got {sorted(score.values)}"
            )
    return ScoreRun(
        method_id=method.method_id,
        method_version=method.version,
        method_config_hash=method.config_hash,
        dataset_snapshot_id=context.dataset_snapshot_id,
        feature_pipeline_version=context.feature_pipeline_version,
        scores=scores,
    )
