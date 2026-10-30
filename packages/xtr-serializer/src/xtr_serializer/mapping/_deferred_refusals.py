"""Refusals met writing a value of a hierarchy, kept until the whole value is written."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

__all__ = ["deferring_refusals", "written_or_deferred"]

_DEFERRED: Final[ContextVar[list[ValueError] | None]] = ContextVar(
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
    refusals: list[ValueError] = []
    token = _DEFERRED.set(refusals)
    try:
        yield refusals
    finally:
        _DEFERRED.reset(token)


def written_or_deferred(value: object, write: Callable[[object], object]) -> object:
    """Write ``value``; or, while refusals are kept, keep the one met writing it, writing ``{}``.

    The serializer of each class a union reads, so that its refusals reach no union.
    """
    try:
        return write(value)
    except ValueError as error:  # how pydantic reports a refusal met writing, whoever raised it
        refusals = _DEFERRED.get()
        if refusals is None:
            raise
        refusals.append(error)
        return {}
