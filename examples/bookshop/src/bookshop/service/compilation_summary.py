"""What the container looked like once compiled, registered by ``CompilationSummaryPass``."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CompilationSummary"]


@dataclass(frozen=True, slots=True)
class CompilationSummary:
    """What the container looked like once compiled — an instance a pass registered.

    Attributes:
        definitions: How many definitions there are.
        aliases: How many aliases there were before they became definitions.
        log: The compiler's log, every pass's messages.
    """

    definitions: int
    aliases: int
    log: tuple[str, ...]
