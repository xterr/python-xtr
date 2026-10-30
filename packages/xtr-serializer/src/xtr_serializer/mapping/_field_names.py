"""The keys a class's fields are read from and written under, as far as its declaration says."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

__all__ = ["field_names_of"]


def field_names_of(kind: type[object]) -> frozenset[str]:
    """Give the names of the fields of ``kind``, and the aliases pydantic recorded for them.

    A dataclass's fields are named by the standard library; pydantic records those of a model and
    of a dataclass it built, aliases included. An alias given in a plain dataclass's annotation is
    only known once pydantic builds its schema, which refuses it there.
    """
    names: set[str] = set()
    if is_dataclass(kind):
        names.update(field.name for field in fields(kind))
    recorded = cast("dict[str, FieldInfo]", getattr(kind, "__pydantic_fields__", {}))
    for name, info in recorded.items():
        aliases = (info.alias, info.serialization_alias, info.validation_alias)
        names.update(alias for alias in aliases if isinstance(alias, str))
        names.add(name)
    return frozenset(names)
