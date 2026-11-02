"""Which class of each hierarchy is written under which name, and which classes were built on."""

from __future__ import annotations

from threading import RLock
from typing import Final, NamedTuple, final

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import MappingError

__all__ = ["REGISTRY", "ClassDiscriminatorRegistry", "Members"]


class Members(NamedTuple):
    """The key a hierarchy writes names under, and the named classes a declared class takes."""

    type_property: str
    names: tuple[tuple[str, type], ...]


@final
class _Hierarchy:
    """One hierarchy: its base, its key, its names, and the classes a schema was built for."""

    __slots__ = ("built", "classes", "names", "root", "type_property")

    def __init__(self, root: type, type_property: str) -> None:
        self.root = root
        self.type_property = type_property
        # In the order the classes were named.
        self.names: dict[str, type] = {}
        self.classes: dict[type, str] = {}
        self.built: set[type] = set()


@final
class ClassDiscriminatorRegistry:
    """Every hierarchy, the names of its classes, and which classes a schema was built for.

    A schema reading a class of a hierarchy holds the names its subclasses had when it was built,
    and pydantic keeps schemas: a model holds those of its fields from the moment it is defined.
    A name added later would never be read by them, so a class is refused a name once a schema was
    built for one of its bases. Threads may register and build at once.
    """

    __slots__ = ("_lock", "_roots")

    def __init__(self) -> None:
        self._roots: dict[type, _Hierarchy] = {}
        self._lock = RLock()

    def add_hierarchy(self, root: type, type_property: str) -> None:
        """Start a hierarchy at ``root``, written under ``type_property``."""
        with self._lock:
            existing = self._hierarchies_of(root)
            if existing:
                raise MappingError(
                    f"{qualified_name_of(root)!r} is already in the hierarchy of "
                    f"{qualified_name_of(existing[0].root)!r}"
                )
            self._roots[root] = _Hierarchy(root, type_property)

    def is_root(self, kind: type) -> bool:
        """Whether ``kind`` is the base of a hierarchy."""
        with self._lock:
            return kind in self._roots

    def in_hierarchy(self, kind: type) -> bool:
        """Whether ``kind`` is in a hierarchy, as its base or under it."""
        with self._lock:
            return bool(self._hierarchies_of(kind))

    def type_property_of(self, kind: type) -> str | None:
        """Give the key the hierarchy of ``kind`` writes names under, ``None`` outside of any.

        Raises:
            MappingError: If ``kind`` derives from the bases of two hierarchies.
        """
        with self._lock:
            hierarchies = self._hierarchies_of(kind)
        if len(hierarchies) > 1:
            roots = " and ".join(repr(qualified_name_of(each.root)) for each in hierarchies)
            raise MappingError(f"{qualified_name_of(kind)!r} is in two hierarchies, of {roots}")
        return hierarchies[0].type_property if hierarchies else None

    def register(self, kind: type, name: str) -> None:
        """Write ``kind`` under ``name`` in its hierarchy, which :meth:`type_property_of` found."""
        with self._lock:
            hierarchy = self._hierarchies_of(kind)[0]
            known = hierarchy.classes.get(kind)
            if known is not None:
                raise MappingError(
                    f"{qualified_name_of(kind)!r} is already named {known!r}; a class has one name"
                )
            taken = hierarchy.names.get(name)
            if taken is not None:
                raise MappingError(
                    f"{qualified_name_of(kind)!r} cannot be named {name!r}: "
                    f"{qualified_name_of(taken)!r} is, in the hierarchy of "
                    f"{qualified_name_of(hierarchy.root)!r}"
                )
            built = next((base for base in kind.__mro__ if base in hierarchy.built), None)
            if built is not None:
                raise MappingError(
                    f"{qualified_name_of(kind)!r} is named after a schema reading "
                    f"{qualified_name_of(built)!r} was built, which would never read it: name "
                    "every class of a hierarchy before a type holding one is used or defined — a "
                    "model holding its own hierarchy is defined with defer_build"
                )
            hierarchy.names[name] = kind
            hierarchy.classes[kind] = name

    def members(self, declared: type) -> Members | None:
        """Give the named classes ``declared`` takes, itself included, or ``None`` outside."""
        with self._lock:
            return self._members(declared)

    def claim(self, declared: type, *, even_unnamed: bool) -> Members | None:
        """Give the named classes ``declared`` takes, for a schema, and keep later names out.

        A schema taking no named class keeps them out only when ``even_unnamed``: one refusing
        the class for having none, which a later name would contradict, rather than a class's
        own schema built before its classes are named.
        """
        with self._lock:
            members = self._members(declared)
            if members is not None and (members.names or even_unnamed):
                self._hierarchy_of(declared).built.add(declared)
            return members

    def _members(self, declared: type) -> Members | None:
        hierarchies = self._hierarchies_of(declared)
        if not hierarchies:
            return None
        hierarchy = hierarchies[0]
        names = tuple(
            (name, kind) for name, kind in hierarchy.names.items() if issubclass(kind, declared)
        )
        return Members(hierarchy.type_property, names)

    def _hierarchy_of(self, kind: type) -> _Hierarchy:
        return self._hierarchies_of(kind)[0]

    def _hierarchies_of(self, kind: type) -> list[_Hierarchy]:
        return [self._roots[base] for base in kind.__mro__ if base in self._roots]


REGISTRY: Final = ClassDiscriminatorRegistry()
