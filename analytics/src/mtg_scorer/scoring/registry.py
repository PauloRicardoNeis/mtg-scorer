"""The score methods available to batch scoring, looked up by identifier."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from types import MappingProxyType

from .base import ScoreMethod
from .constructed import ConstructedMethod
from .foundation import FoundationMethod
from .max_ratio import MaxRatioMethod
from .signature import SignatureMethod


class ScoreMethodRegistry:
    """An immutable set of score methods with unique identifiers."""

    __slots__ = ("_methods",)

    def __init__(self, methods: Iterable[ScoreMethod]) -> None:
        by_id: dict[str, ScoreMethod] = {}
        for method in methods:
            if not method.method_id.strip():
                raise ValueError("method_id cannot be blank")
            if method.method_id in by_id:
                raise ValueError(f"duplicate score method {method.method_id!r}")
            by_id[method.method_id] = method
        self._methods = MappingProxyType(by_id)

    @property
    def method_ids(self) -> tuple[str, ...]:
        return tuple(self._methods)

    def get(self, method_id: str) -> ScoreMethod:
        try:
            return self._methods[method_id]
        except KeyError:
            available = ", ".join(self._methods)
            raise KeyError(f"unknown score method {method_id!r}; available: {available}") from None

    def __contains__(self, method_id: object) -> bool:
        return method_id in self._methods

    def __iter__(self) -> Iterator[ScoreMethod]:
        return iter(self._methods.values())


# Add a new method here; the shared contract tests then cover it automatically.
SCORE_METHODS = ScoreMethodRegistry(
    (ConstructedMethod(), FoundationMethod(), MaxRatioMethod(), SignatureMethod())
)
