"""Types pydantic refuses to build a schema for, each refused in its own way."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, NoReturn, cast

from pydantic import Field
from pydantic.errors import PydanticUserError
from typing_extensions import TypeAliasType, TypedDict  # pydantic reads typing's from 3.12

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import GetCoreSchemaHandler

__all__ = ["REFUSED_TYPES", "Refused", "nested"]


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


def nested(depth: int) -> object:
    """Give a list type nested ``depth`` lists deep around ``int``."""
    type_: object = int
    for _ in range(depth):
        type_ = list[type_]
    return type_


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
