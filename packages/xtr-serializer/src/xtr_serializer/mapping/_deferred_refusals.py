"""Refusals met writing a value of a hierarchy, kept until the whole value is written."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Final, final

from pydantic_core import PydanticSerializationUnexpectedValue

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

__all__ = ["deferring_refusals", "refused_or_deferred", "written_or_deferred"]


@final
class _Kept:
    """The refusals kept, in the order met, and the values refused on a first, strict try."""

    __slots__ = ("refusals", "strictly_refused")

    def __init__(self) -> None:
        self.refusals: list[ValueError] = []
        # By identity: the values being written are alive, and held, until the write is done.
        self.strictly_refused: set[int] = set()


_KEPT: Final[ContextVar[_Kept | None]] = ContextVar(
    "xtr_serializer_deferred_refusals", default=None
)


@contextmanager
def deferring_refusals() -> Generator[list[ValueError]]:
    """Keep each refusal met inside a value of a hierarchy, in the order met, instead of raising it.

    A value of a hierarchy is written by the union of its classes, and pydantic before 2.13 writes
    a value its union refused again, by each class of the union, strictly then not: a refusal deep
    inside a chain of such values is met again for each union holding it, which takes time
    doubling with each one. Kept rather than raised, it reaches no union; the value written then
    is not the value, and is to be thrown away once the first refusal kept is raised.
    """
    kept = _Kept()
    token = _KEPT.set(kept)
    try:
        yield kept.refusals
    finally:
        _KEPT.reset(token)


def written_or_deferred(value: object, write: Callable[[object], object]) -> object:
    """Write ``value``; or, while refusals are kept, keep the one met writing it, writing ``{}``.

    The serializer of each class a union reads, so that its refusals reach no union. pydantic
    before 2.13 first writes the value strictly, refusing what is outside its declared type even
    where it writes it anywhere else, such as ``True`` in an ``int`` field, then writes it again
    as anywhere else: refused on that first try, the value is let through to the next, and its
    refusal is kept only if the next refuses it too.
    """
    kept = _KEPT.get()
    if kept is None:
        return write(value)
    first_try = id(value) not in kept.strictly_refused
    try:
        written = write(value)
    except PydanticSerializationUnexpectedValue as error:
        if first_try:
            kept.strictly_refused.add(id(value))
            raise
        kept.strictly_refused.discard(id(value))
        return refused_or_deferred(error)
    except ValueError as error:  # how pydantic reports a refusal met writing, whoever raised it
        kept.strictly_refused.discard(id(value))
        return refused_or_deferred(error)
    kept.strictly_refused.discard(id(value))
    return written


def refused_or_deferred(error: ValueError) -> object:
    """Raise ``error``; or, while refusals are kept, keep it, writing ``{}`` instead.

    For a refusal no other member of a union holding the value could write it past either.
    """
    kept = _KEPT.get()
    if kept is None:
        raise error
    kept.refusals.append(error)
    return {}
