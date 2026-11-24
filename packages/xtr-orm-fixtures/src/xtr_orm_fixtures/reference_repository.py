"""The objects the fixtures of one run share, by name."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, cast, final

from sqlalchemy import inspect

from .exception import ReferenceExistsError, ReferenceNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["ReferenceRepository"]


@final
class ReferenceRepository:
    """Objects stored by name, per class, for the fixtures of one run.

    A mapped object is stored under its mapped class — the class its rows are
    loaded as — whatever it was built as; any other object under its own
    type. A name is unique per class, so ``"admin"`` may name a user and a
    group at once.

    The objects stay as they were stored: the run never clears its session,
    so a later fixture reads the same object, attached and up to date.
    """

    __slots__ = ("_references",)

    def __init__(self) -> None:
        """Start with no references."""
        self._references: dict[type, dict[str, object]] = {}

    def set_reference(self, name: str, obj: object) -> None:
        """Store ``obj`` under ``name``, replacing what was stored there for its class."""
        self._references.setdefault(_kind_of(obj), {})[name] = obj

    def add_reference(self, name: str, obj: object) -> None:
        """Store ``obj`` under ``name``, which must not be taken for its class yet.

        Raises:
            ReferenceExistsError: If ``name`` is taken for ``obj``'s class.
        """
        kind = _kind_of(obj)
        if name in self._references.get(kind, {}):
            raise ReferenceExistsError(name, kind.__qualname__)
        self.set_reference(name, obj)

    def get_reference[T](self, name: str, cls: type[T]) -> T:
        """Return the ``cls`` object stored under ``name``.

        Raises:
            ReferenceNotFoundError: If nothing is stored under ``name`` for ``cls``.
        """
        stored = self._references.get(cls, {})
        if name not in stored:
            raise ReferenceNotFoundError(name, cls.__qualname__)
        return cast("T", stored[name])

    def has_reference(self, name: str, cls: type) -> bool:
        """Whether an object is stored under ``name`` for ``cls``."""
        return name in self._references.get(cls, {})

    def get_reference_names(self, obj: object) -> tuple[str, ...]:
        """Return every name ``obj`` itself is stored under, in the order stored."""
        stored = self._references.get(_kind_of(obj), {})
        return tuple(name for name, held in stored.items() if held is obj)

    def references_by_class(self) -> Mapping[type, Mapping[str, object]]:
        """Return every reference, by class then name, as it stands now; read only."""
        return MappingProxyType(
            {kind: MappingProxyType(dict(named)) for kind, named in self._references.items()}
        )


def _kind_of(obj: object) -> type:
    """Return the class ``obj`` is stored under: its mapped class when mapped, else its type."""
    state = cast("object", inspect(obj, raiseerr=False))
    mapper = cast("object", getattr(state, "mapper", None))
    mapped = cast("object", getattr(mapper, "class_", None))
    return mapped if isinstance(mapped, type) else type(obj)
