"""How many tokens each place holds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["Marking"]


class Marking:
    """How many tokens each place holds: where a subject is.

    A place is in the marking while it holds a token, and leaves it with its
    last one. A state machine's marking is one token in one place; a
    workflow's can spread over several places, and pile several tokens in one.
    Places are kept in the order they were first marked.

    The marking a workflow returns from applying a transition also carries
    the context the transition ran with.
    """

    __slots__: tuple[str, ...] = ("_context", "_places")

    _places: dict[str, int]
    _context: dict[str, object]

    def __init__(self, places: Mapping[str, int] | None = None) -> None:
        """Mark each of ``places`` with its number of tokens.

        Args:
            places: The number of tokens by place name, each at least 1.

        Raises:
            InvalidArgumentError: If a number of tokens is below 1.
        """
        self._places = {}
        self._context = {}
        for place, token_count in (places or {}).items():
            self.mark(place, token_count)

    def mark(self, place: str, token_count: int = 1) -> None:
        """Put ``token_count`` tokens in ``place``, on top of those it holds.

        Raises:
            InvalidArgumentError: If ``token_count`` is below 1.
        """
        _refuse_below_one(token_count)
        self._places[place] = self._places.get(place, 0) + token_count

    def unmark(self, place: str, token_count: int = 1) -> None:
        """Take ``token_count`` tokens from ``place``; taking its last unmarks it.

        Raises:
            InvalidArgumentError: If ``token_count`` is below 1, ``place`` is
                not marked, or it holds fewer than ``token_count`` tokens.
        """
        _refuse_below_one(token_count)
        if not self.has(place):
            raise InvalidArgumentError(f'The place "{place}" is not marked.')

        initial = self._places[place]
        remaining = initial - token_count
        if remaining < 0:
            raise InvalidArgumentError(
                f'The place "{place}" could not contain a negative token number: '
                f'"{initial}" (initial) - "{token_count}" (nbToken) = "{remaining}".'
            )

        if remaining == 0:
            del self._places[place]
        else:
            self._places[place] = remaining

    def has(self, place: str) -> bool:
        """Tell whether ``place`` holds a token."""
        return place in self._places

    def get_token_count(self, place: str) -> int:
        """Return the number of tokens ``place`` holds, 0 when it is not marked."""
        return self._places.get(place, 0)

    def get_places(self) -> dict[str, int]:
        """Return the number of tokens of every marked place, in the order they were marked.

        A copy: changing it leaves the marking alone, so a count only ever
        changes through :meth:`mark` and :meth:`unmark`, which keep it above 0.
        """
        return dict(self._places)

    def set_context(self, context: Mapping[str, object]) -> None:
        """Keep the context the transition that produced this marking ran with.

        For the workflow, once it has applied a transition; nothing else is
        meant to call it.
        """
        self._context = dict(context)

    def get_context(self) -> dict[str, object]:
        """Return the context the last transition applied ran with, empty before any.

        A copy, like :meth:`get_places`.
        """
        return dict(self._context)


def _refuse_below_one(token_count: int) -> None:
    """Refuse a number of tokens that would not move one.

    Raises:
        InvalidArgumentError: If ``token_count`` is below 1.
    """
    if token_count < 1:
        raise InvalidArgumentError(
            f'The number of tokens must be greater than 0, "{token_count}" given.'
        )
