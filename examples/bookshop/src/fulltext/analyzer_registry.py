"""Which analyzers were declared, by name — one registry per kernel."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from .analyzer_interface import AnalyzerInterface

__all__ = ["AnalyzerRegistry"]


@final
class AnalyzerRegistry:
    """Names every ``@as_analyzer`` class a kernel's scan found.

    The bundle fills it while the container is compiled and registers the very instance with
    ``services.instance(...)``, so two kernels in one process never share one.
    """

    __slots__ = ("_declared",)

    def __init__(self) -> None:
        """Start empty."""
        self._declared: dict[str, type[AnalyzerInterface]] = {}

    def declare(self, name: str, analyzer: type[AnalyzerInterface]) -> None:
        """Record ``analyzer`` under ``name``."""
        self._declared[name] = analyzer

    def names(self) -> tuple[str, ...]:
        """Every declared name, in declaration order."""
        return tuple(self._declared)

    def get(self, name: str) -> type[AnalyzerInterface] | None:
        """The class declared as ``name``, if any."""
        return self._declared.get(name)
