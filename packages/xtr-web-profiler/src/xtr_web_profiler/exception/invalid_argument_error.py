"""A configuration value the web profiler would misread."""

from __future__ import annotations

from .web_profiler_error import WebProfilerError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(WebProfilerError, ValueError):
    """A configuration value the web profiler would misread.

    Also a :class:`ValueError`.
    """
