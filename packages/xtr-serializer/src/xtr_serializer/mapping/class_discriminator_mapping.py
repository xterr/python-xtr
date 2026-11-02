"""The names a class of a hierarchy reads, and the classes they stand for."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import final

from typing_extensions import override

from ._class_discriminator_registry import REGISTRY

__all__ = ["ClassDiscriminatorMapping"]


@final
@dataclass(frozen=True, slots=True)
class ClassDiscriminatorMapping:
    """The key a hierarchy writes class names under, and the classes a declared class takes.

    A snapshot: names registered later are not in it, and it cannot be changed. Mappings compare
    and hash by their key and their names, whatever order the names were given in.

    Attributes:
        type_property: The key each value's class name is written under.
        types_mapping: Each name a field declaring the class reads, and the class it stands for,
            in the order the classes were named.
    """

    type_property: str
    types_mapping: Mapping[str, type] = field(default_factory=dict[str, type])

    def __post_init__(self) -> None:
        """Keep a read-only copy of the names, so the caller's mapping can change on its own."""
        object.__setattr__(self, "types_mapping", MappingProxyType(dict(self.types_mapping)))

    @override
    def __hash__(self) -> int:
        return hash((self.type_property, frozenset(self.types_mapping.items())))

    @classmethod
    def for_class(cls, class_: type) -> ClassDiscriminatorMapping | None:
        """Give the mapping of ``class_`` — itself and the subclasses under it that have a name.

        ``None`` when ``class_`` is in no hierarchy. For the base, that is every name of the
        hierarchy; for a class under it, the names a field declaring that class reads.
        """
        members = REGISTRY.members(class_)
        if members is None:
            return None
        return cls(members.type_property, dict(members.names))
