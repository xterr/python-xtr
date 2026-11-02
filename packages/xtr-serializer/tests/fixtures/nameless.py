"""Classes whose metaclass computes their names, and refuses to while names are refused."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, cast

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Generator

__all__ = ["Nameless", "NamelessCount", "NamelessError", "NamelessThing", "names_refused"]

# The names a class is known by, which code the data carries may compute.
_NAMES: Final = frozenset({"__name__", "__qualname__"})


class Nameless(type):
    """A metaclass computing the names of its classes, as code the data carries may.

    pydantic reads the names as it builds a schema, so they are refused only inside
    :func:`names_refused`, around the step under test.
    """

    refusing: ClassVar[bool] = False

    @override
    def __getattribute__(cls, name: str) -> object:
        if name in _NAMES and Nameless.refusing:
            raise LookupError(name)
        return cast("object", super().__getattribute__(name))


@contextmanager
def names_refused() -> Generator[None]:
    """Make every class of :class:`Nameless` refuse to give its names, for the block."""
    Nameless.refusing = True
    try:
        yield
    finally:
        Nameless.refusing = False


class NamelessThing(metaclass=Nameless):
    """A class pydantic has no schema for, comparing by identity."""


@dataclass(eq=False)
class NamelessCount(metaclass=Nameless):
    """A dataclass comparing by identity, so it never reads back equal."""

    count: int


class NamelessError(Exception, metaclass=Nameless):
    """An error whose class's names its metaclass computes."""
