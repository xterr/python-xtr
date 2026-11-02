"""The adapters a normalizer writes and reads each type with, built once per type."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Final,
    NamedTuple,
    cast,
    final,
)

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

from xtr_serializer._type_cache import TypeCache
from xtr_serializer._type_names import name_of
from xtr_serializer._written_types import written_name_of
from xtr_serializer.exception import MappingError
from xtr_serializer.mapping._declaration_sites import declaring

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
# type is a value known at run time, which is what TypeAliasType takes there. What it makes is
# typed as a class of objects, the type form every pydantic's TypeAdapter takes for T = object.
_alias_of: Final = cast("Callable[[str, object], type[object]]", TypeAliasType)


class Adapter(NamedTuple):
    """What writes the values of one type, and what reads them."""

    writer: TypeAdapter[object]
    reader: SchemaValidator


@final
class AdapterCache:
    """The adapters of the types used last, and why a type has none.

    Kept in a :class:`~xtr_serializer._type_cache.TypeCache`, which says how a type is looked up
    and kept, and how threads share it.
    """

    __slots__ = ("_adapters",)

    def __init__(self) -> None:
        self._adapters: TypeCache[Adapter | str] = TypeCache()

    def get(self, type_: object) -> Adapter | str:
        """Return the adapter of ``type_``, or why it has none, building it on first use.

        A type whose own code raises as it is keyed is built every time, and building refuses it
        without quoting what was raised.
        """
        return self._adapters.get(type_, lambda: build_adapter(type_))


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
    alias of itself or a type nested deeper than building it can go, too. So is a type whose own
    code raises as pydantic reads it, such as a metaclass refusing to show its class: the
    refusal names what was raised by its class alone, as its message may quote the type — but
    for a class hierarchy refusing to be read as its classes were registered, which says why.

    The schema is built as one declaring every class it holds, so that a class of a hierarchy
    reads its classes wherever ``type_`` holds it — through an alias, a new type or at no field
    — whether pydantic built the class yet or not. A class not built yet is read from its fields
    and left unbuilt: building it is pydantic's, on its first use, never one thread's while
    another reads it.
    """
    try:
        with declaring():
            writer = TypeAdapter(_alias_of("Value", type_), config=_EXACT)
            if not writer.pydantic_complete:
                _ = writer.rebuild(raise_errors=True)
        reader = SchemaValidator(cast("CoreSchema", _aware(writer.core_schema)), _EXACT_READING)
    except PydanticSchemaGenerationError:
        return f"pydantic has no schema for {written_name_of(type_)!r}"
    except PydanticUndefinedAnnotation as error:
        return (
            f"pydantic has no schema for {written_name_of(type_)!r}: {error.name!r} is not defined"
        )
    except SchemaError:  # its message may quote the application's values held in the schema
        return f"pydantic refuses the schema of {written_name_of(type_)!r}"
    # How pydantic refuses a type declared in a way it cannot build, as its versions word it, and
    # how building one nested too deep stops.
    except (TypeError, PydanticUserError, RecursionError):
        return f"pydantic cannot build a schema for {written_name_of(type_)!r}"
    except Exception as error:  # noqa: BLE001 - whatever the type's own code raises leaves it unbuilt
        # A hierarchy refusing its classes as registered says why, in this package's words.
        why = (
            error
            if isinstance(error, MappingError)
            else f"building it raised {name_of(type(error))}"
        )
        return f"pydantic cannot build a schema for {written_name_of(type_)!r}: {why}"
    return Adapter(writer, reader)


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
