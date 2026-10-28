"""Every reason a transition cannot be applied to a subject."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from .transition_blocker import TransitionBlocker

__all__ = ["TransitionBlockerList"]


@final
class TransitionBlockerList:
    """Every reason a transition cannot be applied to a subject, in the order they were given.

    Empty means nothing blocks it. Iterating it walks the blockers it held
    when the walk began, so a guard adding one meanwhile is not seen twice.
    """

    __slots__: tuple[str, ...] = ("_blockers",)

    _blockers: list[TransitionBlocker]

    def __init__(self, blockers: Iterable[TransitionBlocker] = ()) -> None:
        """Hold ``blockers``, in order."""
        self._blockers = list(blockers)

    def add(self, blocker: TransitionBlocker) -> None:
        """Add ``blocker`` after those held."""
        self._blockers.append(blocker)

    def has(self, code: str) -> bool:
        """Tell whether a blocker held has ``code``."""
        return any(blocker.get_code() == code for blocker in self._blockers)

    def clear(self) -> None:
        """Forget every blocker: nothing blocks the transition any more."""
        self._blockers = []

    def is_empty(self) -> bool:
        """Tell whether nothing blocks the transition."""
        return not self._blockers

    def __iter__(self) -> Iterator[TransitionBlocker]:
        """Walk the blockers held now, in order."""
        return iter(tuple(self._blockers))

    def __len__(self) -> int:
        """Return how many blockers it holds."""
        return len(self._blockers)
