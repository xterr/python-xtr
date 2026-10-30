"""Dataclasses comparing by the equality ``dataclass`` generates, and by one written by hand."""

from __future__ import annotations

from collections.abc import Callable  # read at run time: dataclass reads its class's annotations
from dataclasses import dataclass, field
from typing import ClassVar, cast

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass
from typing_extensions import override

__all__ = [
    "GENERATED_EQUALITIES",
    "HAND_WRITTEN_EQUALITIES",
    "LabelledParcel",
]


@dataclass
class Plain:
    """A dataclass comparing by the equality ``dataclass`` generates."""

    count: int


@dataclass(frozen=True)
class Frozen:
    """A frozen dataclass."""

    count: int


@dataclass(slots=True)
class Slotted:
    """A dataclass storing its fields in slots."""

    count: int


@dataclass(kw_only=True)
class KeywordOnly:
    """A dataclass taking its fields by keyword only."""

    count: int


@dataclass(order=True)
class Ordered:
    """A dataclass ordering its values by its fields."""

    count: int


@dataclass
class PartlyCompared:
    """A dataclass leaving a field out of its equality."""

    count: int
    note: str = field(default="", compare=False)


@dataclass
class Derived(Plain):
    """A dataclass deriving from another, with an equality generated over all its fields."""

    label: str = ""


class Undecorated(Plain):
    """A class deriving from a dataclass without being one, comparing by its parent's equality."""


@pydantic_dataclass
class Built:
    """A dataclass pydantic built, comparing by the equality ``dataclass`` generates."""

    count: int


GENERATED_EQUALITIES: dict[str, Callable[[int], object]] = {
    "plain": Plain,
    "frozen": Frozen,
    "slots": Slotted,
    "kw-only": lambda count: KeywordOnly(count=count),
    "order": Ordered,
    "compare-false": PartlyCompared,
    "subclass": Derived,
    "undecorated-subclass": Undecorated,
    "pydantic": Built,
}


@dataclass
class User:
    """A dataclass whose own equality takes two users without a key for two different ones."""

    pk: int | None

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, User) and self.pk is not None and self.pk == other.pk

    @override
    def __hash__(self) -> int:
        return id(self)


# An equality written by hand and compiled at run time, as generated ones are.
_compiled: dict[str, object] = {}
exec("def __eq__(self, other):\n    return self is other\n", _compiled)  # noqa: S102 - a fixed literal, compiling it is the case
_compiled_equality = cast("Callable[[object, object], bool]", _compiled["__eq__"])


@dataclass(eq=True)
class CompiledUser:
    """A dataclass whose equality, written by hand, was compiled at run time."""

    pk: int | None

    __eq__: ClassVar[Callable[[object, object], bool]] = _compiled_equality
    __hash__: ClassVar[None] = None  # pyright: ignore[reportIncompatibleMethodOverride] - unhashable, as dataclass makes it


@pydantic_dataclass
class BuiltUser:
    """A dataclass pydantic built, with an equality of its own."""

    pk: int | None

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, BuiltUser) and self.pk is not None and self.pk == other.pk

    @override
    def __hash__(self) -> int:
        return id(self)


HAND_WRITTEN_EQUALITIES: dict[str, Callable[[int | None], object]] = {
    "hand-written": User,
    "exec-compiled": CompiledUser,
    "pydantic": BuiltUser,
}


@pydantic_dataclass(config=ConfigDict(extra="allow"))
class LabelledParcel:
    """A dataclass keeping extra fields, defining a method an extra field may be named after."""

    weight: int

    def label(self) -> str:
        return "parcel"
