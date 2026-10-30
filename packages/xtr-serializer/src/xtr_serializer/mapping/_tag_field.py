"""A class's schema taught to read the key its name is written under, and to keep nothing of it."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final, TypeAlias, cast

from pydantic_core import core_schema

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import MappingError

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_core import CoreSchema

__all__ = ["with_tag_field"]

# A schema as the dict it is, its parts read and copied by their keys.
_Node: TypeAlias = "dict[str, object]"

# What marks the schema of a class this module made, so it is left as it is when met again.
_MARK: Final = "xtr_serializer.class_discriminator"

# The validators pydantic wraps a class's schema in, each holding the class's schema inside.
_WRAPPERS: Final = frozenset({"function-before", "function-after", "function-wrap"})


def with_tag_field(schema: CoreSchema, key: str) -> CoreSchema:
    """Copy the schema of a model or a dataclass, given a field reading ``key`` and dropping it.

    The data of a class in a hierarchy carries its name under ``key``, beside its fields. The
    class must read it rather than take it for a field it lacks — a class closed to other fields
    would refuse it, and one open to them would keep it — and it must read it as the JSON it is,
    as the rest: taking the key out of the data first would hand the class plain Python instead,
    which a strict class reads differently. So the class's fields get one of that name, optional,
    dropped from what they read before the instance is made of it; and the class is written by
    the schema it had, as a field never written still counts among those a value is checked to
    have as it is written inside a union. A model or a dataclass built by itself reads the key
    so, and ignores it.

    The schema returned is a new one down to the class's fields; what they hold is shared. A
    schema made already is returned as it is.

    Raises:
        MappingError: If a field is named or aliased ``key``, the class is a root model, or a
            validator replaces its schema.
    """
    return _as_schema(_tagged(cast("_Node", cast("object", schema)), key))


def _tagged(node: _Node, key: str) -> _Node:
    """Copy ``node``, a class's schema or a validator wrapping it, the class's fields tagged."""
    kind = node["type"]
    if _MARK in cast("_Node", node.get("metadata") or {}):
        return node
    if kind in _WRAPPERS:
        return {**node, "schema": _tagged(cast("_Node", node["schema"]), key)}
    fields = cast("_Node", node.get("schema"))
    if kind == "model" and not node.get("root_model"):
        declared = cast("dict[str, _Node]", fields["fields"])
        named = [(name, field) for name, field in declared.items()]
        tag = core_schema.model_field(_optional_text(), serialization_exclude=True)
        tagged: _Node = {**fields, "fields": {**declared, key: tag}}
    elif kind == "dataclass":
        listed = cast("list[_Node]", fields["fields"])
        named = [(cast("str", field["name"]), field) for field in listed]
        tag = core_schema.dataclass_field(
            key, _optional_text(), kw_only=True, serialization_exclude=True
        )
        tagged = {**fields, "fields": [*listed, tag]}
    else:
        raise MappingError(
            f"a class whose schema is a {kind!r} one, such as a root model, cannot carry {key!r}"
        )
    _refuse_taken(key, qualified_name_of(cast("type", node["cls"])), named)
    original = {part: value for part, value in node.items() if part != "ref"}
    reading = core_schema.no_info_after_validator_function(
        partial(_forget, key=key), _as_schema(tagged)
    )
    copied: _Node = {**node, "schema": reading}
    copied["metadata"] = {**cast("_Node", node.get("metadata") or {}), _MARK: True}
    # A class written by a serializer of its own keeps it.
    _ = copied.setdefault(
        "serialization",
        core_schema.wrap_serializer_function_ser_schema(
            _written_as_declared, schema=_as_schema(original)
        ),
    )
    return copied


def _as_schema(node: object) -> CoreSchema:
    """Take a dict built here for the schema it is."""
    return cast("CoreSchema", node)


def _optional_text() -> CoreSchema:
    """Read the name as text, or nothing: the union holding the class has checked it already."""
    return core_schema.with_default_schema(core_schema.str_schema(), default=None)


def _refuse_taken(key: str, name: str, fields: list[tuple[str, _Node]]) -> None:
    """Refuse a field named ``key``, read from it or written under it."""
    for field, schema in fields:
        keys = (
            field,
            schema.get("serialization_alias"),
            *_read_keys(schema.get("validation_alias")),
        )
        if key in keys:
            raise MappingError(
                f"field {field!r} of {name!r} is named or aliased {key!r}, which its class's name "
                "is written under"
            )


def _read_keys(alias: object) -> tuple[object, ...]:
    """Give the first key of each path a field is read from: an alias, a path, or several paths."""
    if not isinstance(alias, list):
        return (alias,)
    paths = cast("list[object]", alias)
    if paths and isinstance(paths[0], list):
        return tuple(cast("list[object]", path)[0] for path in paths)
    return (paths[0],) if paths else ()


def _written_as_declared(value: object, write: Callable[[object], object]) -> object:
    """Write the value by the schema its class had."""
    return write(value)


def _forget(read: object, *, key: str) -> object:
    """Drop the name from what a class's fields read, and from the names of the fields set.

    A class's fields read a tuple: what each field holds by its name first, then what the class
    makes of the rest — a model's extra fields and the names of the fields set, a dataclass's
    init-only values —, assigning a field included.
    """
    parts = cast("tuple[object, ...]", read)
    fields = cast("_Node", parts[0])
    rest = [cast("set[str]", part) - {key} if isinstance(part, set) else part for part in parts[1:]]
    kept: tuple[object, ...] = ({name: part for name, part in fields.items() if name != key}, *rest)
    return kept
