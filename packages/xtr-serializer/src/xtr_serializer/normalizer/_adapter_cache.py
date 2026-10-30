"""The adapters a normalizer writes and reads each type with, built once per type."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, NamedTuple, cast, final, get_args

from pydantic import ConfigDict, TypeAdapter
from pydantic.dataclasses import is_pydantic_dataclass
from pydantic.errors import (
    PydanticSchemaGenerationError,
    PydanticUndefinedAnnotation,
    PydanticUserError,
)
from pydantic_core import SchemaError, SchemaValidator
from pydantic_core.core_schema import CoreConfig
from typing_extensions import TypeAliasType

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_core import CoreSchema

__all__ = ["Adapter", "AdapterCache", "build_adapter"]

# What makes a value read back as it was written: no conversion on reading, no NaN or infinity,
# bytes as base64 rather than as text they may not be, durations in ISO 8601.
_EXACT: Final = ConfigDict(
    strict=True,
    allow_inf_nan=False,
    ser_json_bytes="base64",
    val_json_bytes="base64",
    ser_json_timedelta="iso8601",
)

# The part of it that reading takes, for the reader built from the writer's schema.
_EXACT_READING: Final = CoreConfig(strict=True, allow_inf_nan=False, val_json_bytes="base64")

# The parts of a schema the reader leaves as they are, by the type of schema: those holding the
# application's values rather than schemas, and how a value is written, which reading never uses.
_KEPT: Final = frozenset({"metadata", "serialization"})
_VALUES: Final = {
    "default": _KEPT | {"default"},
    "literal": _KEPT | {"expected"},
    "enum": _KEPT | {"members"},
    "union": _KEPT | {"custom_error_context"},
    "tagged-union": _KEPT | {"custom_error_context"},
    "custom-error": _KEPT | {"custom_error_context"},
}

# The parts of a schema mapping names the application chose to schemas, by the type of schema: a
# typed dict's fields, a tagged union's tags. Each name is the application's, never a part.
_NAMED: Final = {"typed-dict": "fields", "tagged-union": "choices"}

# Type checkers read an alias only as a statement naming a type written in the code; here the
# type is a value known at run time, which is what TypeAliasType takes there.
_alias_of: Final = cast("Callable[[str, object], object]", TypeAliasType)

# How many types a cache keeps the adapter of. A type expression built per call, such as
# Annotated[int, Field(ge=0)], is a new key each time; the least recently used goes first.
_CACHE_SIZE: Final = 256


class Adapter(NamedTuple):
    """What writes the values of one type, and what reads them."""

    writer: TypeAdapter[object]
    reader: SchemaValidator


@final
class AdapterCache:
    """The adapters of the types used last, and why a type has none.

    A union's members count in the order written, as pydantic tries them in that order.
    """

    __slots__ = ("_adapters",)

    def __init__(self) -> None:
        # Oldest use first: a type used again is moved to the end.
        self._adapters: dict[object, Adapter | str] = {}

    def get(self, type_: object) -> Adapter | str:
        """Return the adapter of ``type_``, or why it has none, building it on first use."""
        key = _key_of(type_)
        try:
            _ = hash(key)
        except TypeError:  # a type expression that cannot be hashed is built every time
            return build_adapter(type_)
        adapter = self._adapters.pop(key, None)
        if adapter is None:
            adapter = build_adapter(type_)
        self._adapters[key] = adapter
        if len(self._adapters) > _CACHE_SIZE:
            del self._adapters[next(iter(self._adapters))]
        return adapter


def build_adapter(type_: object) -> Adapter | str:
    """Build the adapter of ``type_`` under the exact configuration, or say why it has none.

    pydantic refuses a configuration for a bare model, dataclass or typed dict; given one for an
    alias of the type, it applies it to the type and to what the type holds. A type naming what
    is not defined at run time, such as a class imported for type checkers only, gets an adapter
    pydantic finishes on first use; it is finished here, so the name is reported at once.

    The reader is the writer's schema with every ``datetime`` that declares no rule about its
    zone made to require one: a naive datetime names no instant, so it reads back as none in
    particular. ``NaiveDatetime`` and ``AwareDatetime`` keep their rule. A model, and a dataclass
    pydantic built, keep their own rules, wherever they sit: pydantic may read one with the
    validator its class was built with rather than with the schema holding it, as its versions
    decide differently, so the reader leaves them as they are for them to read alike on all.
    A schema pydantic refuses, such as one a class's schema hook returns, is said to be refused,
    and a type pydantic cannot build one for, such as a discriminator on what is no union, an
    alias of itself or a type nested deeper than building it can go, too.
    """
    name = type_.__qualname__ if isinstance(type_, type) else repr(type_)
    try:
        writer: TypeAdapter[object] = TypeAdapter(_alias_of("Value", type_), config=_EXACT)
        if not writer.pydantic_complete:
            _ = writer.rebuild(raise_errors=True)
        reader = SchemaValidator(cast("CoreSchema", _aware(writer.core_schema)), _EXACT_READING)
    except PydanticSchemaGenerationError:
        return f"pydantic has no schema for {name!r}"
    except PydanticUndefinedAnnotation as error:
        return f"pydantic has no schema for {name!r}: {error.name!r} is not defined"
    except SchemaError:  # its message may quote the application's values held in the schema
        return f"pydantic refuses the schema of {name!r}"
    # How pydantic refuses a type declared in a way it cannot build, as its versions word it, and
    # how building one nested too deep stops.
    except (TypeError, PydanticUserError, RecursionError):
        return f"pydantic cannot build a schema for {name!r}"
    return Adapter(writer, reader)


def _key_of(type_: object) -> object:
    """Key ``type_`` by its arguments in order, which a union's equality leaves out."""
    arguments: tuple[object, ...] = get_args(type_)
    return (type_, tuple(_key_of(argument) for argument in arguments))


def _aware(schema: object) -> object:
    """Copy ``schema``, every datetime declaring no rule about its zone made to require one.

    The schema is walked by its structure: each schema is looked into by its type, which tells
    the parts holding schemas from those holding the application's values, such as a default or
    an enum's members, kept as they are, and from those keyed by the application's names, such
    as a typed dict's fields, whose every name is looked past. Only the plain dicts, lists and
    tuples a schema is built of are looked into: a value of a subclass of one — an enum member
    that is a tuple, say — is the application's, kept as it is. The schema of a model, or of a
    dataclass pydantic built, is kept as it is too.
    """
    kind = type(schema)
    if kind is list or kind is tuple:
        parts = [_aware(part) for part in cast("list[object]", schema)]
        return parts if kind is list else tuple(parts)
    if kind is not dict:
        return schema
    node = cast("dict[str, object]", schema)
    # A schema's type is text; the dicts holding something else there are kept or looked past.
    schema_type = cast("str", node.get("type", ""))
    if schema_type == "model" or (
        schema_type == "dataclass" and is_pydantic_dataclass(cast("type", node["cls"]))
    ):
        return node
    kept, named = _VALUES.get(schema_type, _KEPT), _NAMED.get(schema_type)
    copied: dict[str, object] = {}
    for key, part in node.items():
        if key in kept:
            copied[key] = part
        elif key == named:
            mapping = cast("dict[object, object]", part)
            copied[key] = {name: _aware(item) for name, item in mapping.items()}
        else:
            copied[key] = _aware(part)
    if schema_type == "datetime":
        _ = copied.setdefault("tz_constraint", "aware")
    return copied
