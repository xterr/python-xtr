"""Configuration for the fulltext bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from xtr_clock.bundle import ClockConfig
from xtr_dependency_injection import AliasOf

__all__ = ["FulltextConfig"]


@dataclass(frozen=True, slots=True)
class FulltextConfig:
    """What the bundle builds the index and engine from. Buildable with no arguments.

    The annotations are read at runtime (``AliasOf`` is found through them), so every type
    they name is imported for real, never under ``TYPE_CHECKING``.

    Attributes:
        pipeline: Analyzer names, in the order they run.
        stop_words: Words the ``stop_words`` analyzer drops.
        max_results: The most hits one query returns.
        min_score: The least score a hit needs, between 0 and 1.
        slow_query_ms: Queries slower than this are recorded as slow.
        clock: Forwarded, when set, to the ``clock`` bundle's config — the application
            configures the clock the index stamps with from here, through ``AliasOf``.
    """

    pipeline: tuple[str, ...] = ("lowercase", "words")
    stop_words: tuple[str, ...] = ()
    max_results: int = 10
    min_score: float = 0.0
    slow_query_ms: float = 25.0
    clock: Annotated[ClockConfig | None, AliasOf("clock")] = None

    def __post_init__(self) -> None:
        """Refuse values the engine could not honour.

        While the kernel builds, a numeric ``env()`` placeholder carries its ``default`` (or
        ``0``), so these checks run against it; the resolved copy a service receives is
        validated again.

        Raises:
            ValueError: If the pipeline is empty, or a number is out of range.
        """
        if not self.pipeline:
            raise ValueError("pipeline must name at least one analyzer")
        if self.max_results < 0:
            raise ValueError(f"max_results must not be negative, got {self.max_results}")
        if not 0.0 <= self.min_score <= 1.0:
            raise ValueError(f"min_score must be between 0 and 1, got {self.min_score}")
