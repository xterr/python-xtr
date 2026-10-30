"""Types pydantic refuses to build a schema for, each refused in its own way."""

from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Annotated, Literal, NoReturn, cast

from pydantic import Field
from pydantic.errors import PydanticUserError
from typing_extensions import (  # pydantic reads typing's TypedDict from 3.12
    TypeAliasType,
    TypedDict,
    override,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import GetCoreSchemaHandler

__all__ = [
    "REFUSED_TYPES",
    "TYPE_CODE_RAISED",
    "Clash",
    "Disguised",
    "OtherClash",
    "Refused",
    "Sealed",
    "Unhashable",
    "Unhashed",
    "Unprintable",
    "Unshown",
    "nested",
    "optionals",
]

# What a type's own code raises with, which no error must quote.
TYPE_CODE_RAISED = "type-code-ran-4f9a"


class Tagged(TypedDict):
    """A union member carrying the tag its union is discriminated on."""

    kind: Literal["tagged"]


class Untagged(TypedDict):
    """A union member lacking the tag its union is discriminated on."""

    other: Literal["untagged"]


class Refused:
    """A class whose schema hook refuses it, as pydantic refuses a type declared wrongly."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: object, handler: GetCoreSchemaHandler
    ) -> NoReturn:
        raise PydanticUserError("refused", code=None)


class Unshowing(type):
    """A metaclass refusing to show its classes."""

    @override
    def __repr__(cls) -> str:
        raise LookupError


class Unshown(metaclass=Unshowing):
    """A class that refuses to be shown, which pydantic shows as it builds its schema."""


class Unprintable:
    """What is not a type, and refuses to be shown."""

    @override
    def __repr__(self) -> str:
        raise LookupError


class Sealing(type):
    """A metaclass refusing every attribute of its classes, their names and class included."""

    @override
    def __getattribute__(cls, name: str) -> NoReturn:
        raise LookupError(name)


class Sealed(metaclass=Sealing):
    """A class none of whose attributes can be read."""


class Unhashing(type):
    """A metaclass refusing to hash its classes."""

    @override
    def __hash__(cls) -> NoReturn:
        raise LookupError(TYPE_CODE_RAISED)


class Unhashed(metaclass=Unhashing):
    """A class that refuses to be hashed."""


class Unhashable:
    """What is not a type, and refuses to be hashed."""

    @override
    def __hash__(self) -> NoReturn:
        raise LookupError(TYPE_CODE_RAISED)


class Clashing(type):
    """A metaclass hashing all its classes alike, and refusing to compare them."""

    @override
    def __hash__(cls) -> int:
        return 0

    @override
    def __eq__(cls, other: object) -> NoReturn:
        raise LookupError(TYPE_CODE_RAISED)


class Clash(metaclass=Clashing):
    """A class hashed as :class:`OtherClash` is, refusing to be compared with it."""


class OtherClash(metaclass=Clashing):
    """A class hashed as :class:`Clash` is, refusing to be compared with it."""


class Disguised:
    """What is not a type, and refuses to tell its class."""

    @property
    @override
    def __class__(self) -> NoReturn:
        raise LookupError(TYPE_CODE_RAISED)

    @__class__.setter
    def __class__(self, value: type) -> NoReturn:
        raise LookupError(TYPE_CODE_RAISED)


def nested(depth: int) -> object:
    """Give a list type nested ``depth`` lists deep around ``int``."""
    type_: object = int
    for _ in range(depth):
        type_ = list[type_]
    return type_


def optionals(depth: int) -> object:
    """Give a type nested ``depth`` deep in annotated optionals around ``int``.

    Each is a union of the typing module's, which an annotated type makes with ``None``.
    """
    type_: object = int
    for _ in range(depth):
        type_ = _or(_item(Annotated, (type_, "x")), None)
    return type_


# A type built from another known at run time only, which type checkers read as no type.
_item = cast("Callable[[object, tuple[object, ...]], object]", operator.getitem)
_or = cast("Callable[[object, object], object]", operator.or_)


# Type checkers read an alias only as a statement naming a type; this one is built at run time,
# its value its own name, which pydantic reads as a reference to itself.
_alias_of = cast("Callable[[str, object], object]", TypeAliasType)

REFUSED_TYPES: dict[str, object] = {
    "integer-discriminated": Annotated[int, Field(discriminator="kind")],
    "untagged-member": Annotated[Tagged | Untagged, Field(discriminator="kind")],
    "self-alias": _alias_of("Loop", "Loop"),
    "refusing-hook": Refused,
    "too-deep": nested(300),
}
