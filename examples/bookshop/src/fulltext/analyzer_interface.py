"""What one step of the analysis pipeline answers to."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["AnalyzerInterface"]


@runtime_checkable
class AnalyzerInterface(Protocol):
    """Turns the terms produced so far into the terms the next step sees.

    The pipeline starts from ``[text]``; a splitting analyzer returns more terms than it was
    given, a filtering one fewer.
    """

    def analyze(self, terms: list[str], /) -> list[str]:
        """Return the terms after this step."""
        ...
