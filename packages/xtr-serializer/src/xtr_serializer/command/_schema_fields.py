"""The fields of a class as pydantic's JSON schema of it describes them, one row each."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, NamedTuple, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic import TypeAdapter
    from pydantic.json_schema import JsonSchemaMode

__all__ = ["FieldRow", "field_rows", "type_name_of"]

_Schema = dict[str, object]

_DEEPEST: Final = 8
"""How many references deep a type is named, past which it is written ``...``."""


class FieldRow(NamedTuple):
    """One field: its name, the name it is read or written under, its type, and its default."""

    name: str
    serialized_name: str
    type_name: str
    required: str
    default: str


def field_rows(
    writer: TypeAdapter[object], mode: JsonSchemaMode, member: int | None = None
) -> list[FieldRow] | None:
    """Describe each field of what ``writer`` writes, in ``mode``; ``None`` for no object.

    The names it is read or written under are the schema's by alias, and its own names the
    schema's by name, field for field. A class of a hierarchy is written as a union of the named
    classes it takes, in the order they were named: ``member`` is the place of the class in it.
    """
    aliased = _object_of(writer.json_schema(mode=mode, by_alias=True), member)
    named = _object_of(writer.json_schema(mode=mode, by_alias=False), member)
    if aliased is None or named is None:
        return None
    schema, defs = aliased
    properties = cast("Mapping[str, _Schema]", schema.get("properties", {}))
    required = cast("list[str]", schema.get("required", []))
    names = list(cast("Mapping[str, object]", named[0].get("properties", {})))
    return [
        FieldRow(
            name,
            serialized_name,
            type_name_of(field, defs),
            "yes" if serialized_name in required else "no",
            json.dumps(field["default"]) if "default" in field else "",
        )
        for name, (serialized_name, field) in zip(names, properties.items(), strict=True)
    ]


def type_name_of(schema: Mapping[str, object], defs: Mapping[str, _Schema], depth: int = 0) -> str:
    """Name the type ``schema`` describes, as a reader of the table would write it."""
    if depth > _DEEPEST:
        return "..."
    if "$ref" in schema:
        return _referenced(cast("str", schema["$ref"]), defs, depth)
    choices = schema.get("anyOf", schema.get("oneOf"))
    if choices is not None:
        alternatives = cast("list[_Schema]", choices)
        return " | ".join(type_name_of(choice, defs, depth + 1) for choice in alternatives)
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return " | ".join(json.dumps(choice) for choice in cast("list[object]", schema["enum"]))
    return _typed(schema, defs, depth)


def _referenced(reference: str, defs: Mapping[str, _Schema], depth: int) -> str:
    """Name the type a reference points to: its title, or what it describes when it has none."""
    name = reference.rpartition("/")[2]
    target = defs.get(name)
    if target is None:
        return name
    title = target.get("title")
    return cast("str", title) if title is not None else type_name_of(target, defs, depth + 1)


def _typed(schema: Mapping[str, object], defs: Mapping[str, _Schema], depth: int) -> str:
    """Name the type a schema's ``type`` says, with what it holds."""
    kind = schema.get("type")
    if isinstance(kind, list):
        return " | ".join(cast("list[str]", kind))
    if kind == "array":
        return _array(schema, defs, depth)
    if kind == "object":
        values = schema.get("additionalProperties")
        if isinstance(values, dict):
            return f"object[{type_name_of(cast('_Schema', values), defs, depth + 1)}]"
        return cast("str", schema.get("title", "object"))
    if kind is None:
        return "any"
    shape = schema.get("format")
    return f"{kind} ({shape})" if shape is not None else cast("str", kind)


def _array(schema: Mapping[str, object], defs: Mapping[str, _Schema], depth: int) -> str:
    """Name an array: of the items it holds, or of each item in place for a tuple."""
    if "prefixItems" in schema:
        items = cast("list[_Schema]", schema["prefixItems"])
        return f"array[{', '.join(type_name_of(item, defs, depth + 1) for item in items)}]"
    if "items" in schema:
        return f"array[{type_name_of(cast('_Schema', schema['items']), defs, depth + 1)}]"
    return "array"


def _object_of(schema: _Schema, member: int | None) -> tuple[_Schema, Mapping[str, _Schema]] | None:
    """Find the object ``schema`` describes — or, given ``member``, that member of its union.

    ``None`` when it is no object. A union of one class is that class: pydantic writes it as the
    class alone.
    """
    defs = cast("Mapping[str, _Schema]", schema.get("$defs", {}))
    found = _resolved(schema, defs)
    if member is not None and "oneOf" in found:
        found = _resolved(cast("list[_Schema]", found["oneOf"])[member], defs)
    if found.get("type") != "object":
        return None
    return found, defs


def _resolved(schema: _Schema, defs: Mapping[str, _Schema]) -> _Schema:
    """Follow ``schema``'s references to the schema they end at, which pydantic always writes."""
    while "$ref" in schema:
        schema = defs[cast("str", schema["$ref"]).rpartition("/")[2]]
    return schema
