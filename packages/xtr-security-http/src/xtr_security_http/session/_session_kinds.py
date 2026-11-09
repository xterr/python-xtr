"""Naming a class in a session, and finding it again among the classes already loaded.

A session store sits outside the process, so a class name it hands back is
data, never an instruction: nothing here imports a module, reads a name off
one, or builds a class a session names. A kind is looked up only among the
subclasses of a root the caller already holds — the classes the process loaded
itself — so a forged kind can name nothing, or a class that was always meant
to be rebuilt from a session, and nothing else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["kind_of", "loaded_kind"]

_T = TypeVar("_T")


def kind_of(cls: type) -> str:
    """Return the name a session keeps ``cls`` under: its module, a colon, its qualified name."""
    return f"{cls.__module__}:{cls.__qualname__}"


def loaded_kind(root: type[_T], kind: str) -> type[_T] | None:
    """Return the loaded subclass of ``root`` a session names ``kind``, or ``None``.

    ``root``'s subclasses are walked as they are now, recursively; ``root``
    itself is not one of them. Two loaded classes may share a kind — a class a
    decorator remade, whose first spelling lingers until it is collected, or a
    module loaded twice — and the one made last is answered, since it is the
    one its module holds now.
    """
    found: type[_T] | None = None
    for subclass in _subclasses_of(root):
        if kind_of(subclass) == kind:
            found = subclass
    return found


def _subclasses_of(root: type[_T]) -> Iterator[type[_T]]:
    """Yield every subclass of ``root`` loaded now, depth first, each in the order it was made."""
    for subclass in root.__subclasses__():
        yield subclass
        yield from _subclasses_of(subclass)
