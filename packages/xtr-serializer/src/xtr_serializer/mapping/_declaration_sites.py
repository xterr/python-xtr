"""Whether the schema being built is a type's, every class it holds declared there."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Generator

__all__ = ["declaring", "is_declaring"]

_DECLARING: Final[ContextVar[bool]] = ContextVar("xtr_serializer_declaring", default=False)


@contextmanager
def declaring() -> Generator[None]:
    """Build a type's schema, in which every class of a hierarchy asked for its own is declared.

    pydantic asks a class for its schema both as it builds the class itself and where a type
    holds it, and tells the two apart by nothing the class or the question shows. A type's schema
    built here is never a class's own build: pydantic reads a class it has not built from its
    fields, inline, and leaves the class as it is. Kept per thread, and per task, so that a class
    another thread builds meanwhile is still built as itself.
    """
    token = _DECLARING.set(True)
    try:
        yield
    finally:
        _DECLARING.reset(token)


def is_declaring() -> bool:
    """Whether the schema being built is a type's, built in :func:`declaring`."""
    return _DECLARING.get()
