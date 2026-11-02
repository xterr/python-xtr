"""A class as a union reads it: the key its name is written under taken out of the data first."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final, TypeAlias, cast

from pydantic_core import core_schema, to_json

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import MappingError

from ._deferred_refusals import written_or_deferred

if TYPE_CHECKING:
    from pydantic_core import CoreSchema

__all__ = ["class_choice"]

# A schema as the dict it is, its parts read by their keys.
_Node: TypeAlias = "dict[str, object]"

# The validators pydantic wraps a class's schema, or its fields, in: each holds what it wraps.
_WRAPPERS: Final = frozenset({"function-before", "function-after", "function-wrap"})


def class_choice(own: CoreSchema, kind: type, key: str, ref: str) -> CoreSchema:
    """Read ``kind`` by ``own``, its schema, from data naming it under ``key``; keep it at ``ref``.

    The class's schema is left as it is, and read from the data with the name taken out: as
    Python, it is read as it is; as JSON, the rest is written back to JSON and read as such, for a
    strict class reads a date or a tuple from JSON text but not from the Python that JSON is
    parsed into. Its JSON schema is the class's own.

    ``own`` is kept by reference, its own: it is passed on with the schema returned.

    Raises:
        MappingError: If a field of ``kind`` is named ``key``, or read from it or written under it.
    """
    _refuse_taken(cast("_Node", cast("object", own)), kind, key)
    by_ref = core_schema.definition_reference_schema(cast("str", own.get("ref")))
    return core_schema.json_or_python_schema(
        json_schema=core_schema.no_info_before_validator_function(
            partial(_without_as_json, key=key),
            core_schema.json_schema(by_ref),
            json_schema_input_schema=by_ref,
        ),
        python_schema=core_schema.no_info_before_validator_function(
            partial(_without, key=key), by_ref, json_schema_input_schema=by_ref
        ),
        ref=ref,
        # Written by the class's own schema, named so the union holding it knows that a value it
        # refused on a strict first try is to be written again as anywhere else.
        serialization=core_schema.wrap_serializer_function_ser_schema(
            written_or_deferred, schema=by_ref
        ),
    )


def _without(data: object, *, key: str) -> object:
    """Copy ``data``, an object of a dict, without ``key``; give anything else as it is.

    The dict is read by the built-in methods, past any override of its class's, and ``key`` is
    told among the keys that are text exactly, compared as text: taking it out by a lookup would
    compare it with a key of the data's hashed alike, running that key's code.
    """
    if not issubclass(type(data), dict):
        return data
    items = dict[object, object].items(cast("dict[object, object]", data))
    return {at: item for at, item in items if type(at) is not str or at != key}


def _without_as_json(data: object, *, key: str) -> bytes:
    """Write ``data``, JSON as pydantic parsed it, back to JSON without ``key``.

    NaN and infinity are written as they were read, so that the class refuses them where it does.
    """
    return to_json(_without(data, key=key), inf_nan_mode="constants")


def _refuse_taken(own: _Node, kind: type, key: str) -> None:
    """Refuse a field of ``own``, the schema of ``kind``, named ``key``, read or written there."""
    for name, field in _fields_of(own):
        keys = (name, field.get("serialization_alias"), *_read_keys(field.get("validation_alias")))
        if key in keys:
            raise MappingError(
                f"field {name!r} of {qualified_name_of(kind)!r} is named or aliased {key!r}, "
                "which its class's name is written under"
            )


def _fields_of(own: _Node) -> list[tuple[str, _Node]]:
    """Give the fields of a model's or a dataclass's schema, past the validators wrapping it.

    Read only: a schema of another kind has no fields of its own to give.
    """
    node = _unwrapped(own)
    if node["type"] not in {"model", "dataclass"}:
        return []
    fields = _unwrapped(cast("_Node", node["schema"])).get("fields")
    if isinstance(fields, dict):
        return list(cast("dict[str, _Node]", fields).items())
    listed = cast("list[_Node]", fields or [])
    return [(cast("str", field["name"]), field) for field in listed]


def _unwrapped(node: _Node) -> _Node:
    """Give what the validators wrapping ``node`` wrap."""
    while node["type"] in _WRAPPERS:
        node = cast("_Node", node["schema"])
    return node


def _read_keys(alias: object) -> tuple[object, ...]:
    """Give the first key of each path a field is read from: an alias, a path, or several paths."""
    if not isinstance(alias, list):
        return (alias,)
    paths = cast("list[object]", alias)
    if paths and isinstance(paths[0], list):
        return tuple(cast("list[object]", path)[0] for path in paths)
    return (paths[0],) if paths else ()
