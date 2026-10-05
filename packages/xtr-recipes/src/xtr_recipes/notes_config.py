"""The notes a recipe prints once it is applied, never written to disk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["NotesConfig"]


@final
@dataclass(frozen=True, slots=True)
class NotesConfig:
    """What a recipe cannot do for an application, told to the person instead.

    A recipe is declarative: it writes files, lists bundles, adds environment
    and ignore lines. Three things remain that it either must not do or cannot
    do, so it prints them for someone to act on — which is why they are kept
    apart rather than folded into one blob of text.

    Attributes:
        steps: Manual changes an *Activate* or *Configure* step lists that a
            declarative recipe cannot make, such as editing application code.
        check: Commands that show the package working, for after the sync.
        run: Commands that put the package to work.
    """

    steps: tuple[str, ...] = ()
    check: tuple[str, ...] = ()
    run: tuple[str, ...] = ()
