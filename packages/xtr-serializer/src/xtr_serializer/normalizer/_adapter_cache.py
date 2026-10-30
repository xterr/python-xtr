"""The adapters a normalizer writes and reads each type with, built once per type."""

from __future__ import annotations

from types import NoneType, UnionType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Final,
    Literal,
    NamedTuple,
    cast,
    final,
    get_args,
    get_origin,
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
from typing_extensions import TypeAliasType, override

from xtr_serializer._type_names import name_of, qualified_name_of

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

# What a type is called when naming it raises, or goes deeper than the stack.
_UNNAMED: Final = "a type that cannot be named"

# The union the typing module builds, which ``X | Y`` builds too where ``X`` is one of its forms;
# the same class as the other on Python 3.14.
_TYPING_UNION: Final = cast("object", get_origin(Literal[0] | None))


class Adapter(NamedTuple):
    """What writes the values of one type, and what reads them."""

    writer: TypeAdapter[object]
    reader: SchemaValidator


@final
class _Key:
    """A type's key, hashed once as it is made, and compared without letting the type raise.

    A type's own code may hash or compare it differently, or raise, from one call to the next.
    Hashed once, a kept key is found, moved and evicted by the hash it was kept under, never
    hashing the type again; compared, a key whose type's code raises is taken for another, so a
    lookup of any type never fails for a key kept before it.
    """

    __slots__ = ("_hash", "_key")

    def __init__(self, key: object) -> None:
        self._key = key
        self._hash = hash(key)

    @override
    def __hash__(self) -> int:
        return self._hash

    @override
    def __eq__(self, other: object) -> bool:
        try:
            return self._key == cast("_Key", other)._key  # only keys are kept
        except Exception:  # noqa: BLE001 - whatever the type's own code raises makes them differ
            return False


@final
class AdapterCache:
    """The adapters of the types used last, and why a type has none.

    A union's members count in the order written, as pydantic tries them in that order.
    """

    __slots__ = ("_adapters",)

    def __init__(self) -> None:
        # Oldest use first: a type used again is moved to the end.
        self._adapters: dict[_Key, Adapter | str] = {}

    def get(self, type_: object) -> Adapter | str:
        """Return the adapter of ``type_``, or why it has none, building it on first use.

        Keying a type runs its own code — reading its class to take it apart, hashing it — which
        may raise, as may a type nested deeper than keying it can go. Such a type is not kept but
        built every time, and building refuses it without quoting what was raised. A type that
        raises only later, as it is compared with another kept or asked for its hash again, is
        no longer found: it is built again, and its kept adapter goes when its turn comes.
        """
        try:
            key = _Key(_key_of(type_))
        except Exception:  # noqa: BLE001 - whatever the type's own code raises leaves it unkept
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
    alias of itself or a type nested deeper than building it can go, too. So is a type whose own
    code raises as pydantic reads it, such as a metaclass refusing to show its class: the
    refusal names what was raised by its class alone, as its message may quote the type.
    """
    try:
        writer: TypeAdapter[object] = TypeAdapter(_alias_of("Value", type_), config=_EXACT)
        if not writer.pydantic_complete:
            _ = writer.rebuild(raise_errors=True)
        reader = SchemaValidator(cast("CoreSchema", _aware(writer.core_schema)), _EXACT_READING)
    except PydanticSchemaGenerationError:
        return f"pydantic has no schema for {_name_of(type_)!r}"
    except PydanticUndefinedAnnotation as error:
        return f"pydantic has no schema for {_name_of(type_)!r}: {error.name!r} is not defined"
    except SchemaError:  # its message may quote the application's values held in the schema
        return f"pydantic refuses the schema of {_name_of(type_)!r}"
    # How pydantic refuses a type declared in a way it cannot build, as its versions word it, and
    # how building one nested too deep stops.
    except (TypeError, PydanticUserError, RecursionError):
        return f"pydantic cannot build a schema for {_name_of(type_)!r}"
    except Exception as error:  # noqa: BLE001 - whatever the type's own code raises leaves it unbuilt
        raised = name_of(type(error))
        return (
            f"pydantic cannot build a schema for {_name_of(type_)!r}: building it raised {raised}"
        )
    return Adapter(writer, reader)


def _name_of(type_: object) -> str:
    """Name ``type_`` as written, or by a fixed name when naming it raises.

    A class is named by its qualified name, read past its metaclass, in most type expressions:
    the expression is taken apart rather than shown, which would ask each class in it for its
    name, and a class is told apart before anything else is read of it, which would ask its
    metaclass. Not in all: taking apart ``Callable[[X], ...]`` with a single parameter is left to
    the typing module, which reads attributes of ``X``, so a class refusing those leaves the
    whole type named "a type that cannot be named". Showing what is neither a class nor an
    expression — an annotation's metadata, a literal's values — runs their own code, which may
    raise; so may a type nested deeper than the stack.
    """
    try:
        return _written(type_)
    except Exception:  # noqa: BLE001 - whatever naming runs leaves the type unnamed, not the call failed
        return _UNNAMED


def _written(type_: object) -> str:
    """Write ``type_`` as it is written in code, its classes by their qualified names."""
    if type_ is not NoneType and isinstance(type_, type):
        return qualified_name_of(type_)
    origin = cast("object", get_origin(type_))
    arguments: tuple[object, ...] = get_args(type_)
    if origin is None:
        return _written_alone(type_)
    if origin is _TYPING_UNION or origin is UnionType:
        return " | ".join(map(_written, arguments))
    if origin is Literal:
        return f"Literal[{', '.join(map(repr, arguments))}]"
    if origin is Annotated:
        metadata = ", ".join(map(repr, arguments[1:]))
        return f"Annotated[{_written(arguments[0])}, {metadata}]"
    return f"{_written(origin)}[{', '.join(map(_written, arguments))}]"


def _written_alone(type_: object) -> str:
    """Write what takes no arguments, a class aside: ``None``, ``...``, a callable's parameters."""
    if type_ is NoneType or type_ is None:
        return "None"
    if type_ is Ellipsis:
        return "..."
    if isinstance(type_, list):
        return f"[{', '.join(map(_written, cast('list[object]', type_)))}]"
    return repr(type_)


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
