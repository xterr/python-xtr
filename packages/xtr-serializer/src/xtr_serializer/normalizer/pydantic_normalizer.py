"""Values turned into plain data and back by pydantic, under one configuration for exactness."""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Final, Literal, TypeVar, cast, final, get_args, overload

from pydantic import ConfigDict, TypeAdapter, ValidationError
from pydantic.errors import PydanticSchemaGenerationError, PydanticUndefinedAnnotation
from pydantic_core import from_json, to_json
from typing_extensions import TypeAliasType, override

from xtr_serializer.exception import (
    CircularReferenceError,
    InvalidArgumentError,
    NotNormalizableValueError,
    PartialDenormalizationError,
)

from ._validation_refusals import refusals_of
from .denormalizer_interface import COLLECT_DENORMALIZATION_ERRORS, DenormalizerInterface
from .normalizer_interface import NormalizerInterface
from .pydantic_normalizer_keys import (
    ALLOW_EXTRA_ATTRIBUTES,
    ATTRIBUTES,
    BY_ALIAS,
    FROM_ATTRIBUTES,
    IGNORED_ATTRIBUTES,
    POPULATE_BY_NAME,
    SKIP_DEFAULT_VALUES,
    SKIP_NULL_VALUES,
    SKIP_UNSET_VALUES,
    STRICT,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_core import ErrorDetails

    from xtr_serializer.context.context import Context
    from xtr_serializer.normalized_value import NormalizedValue
    from xtr_serializer.supported_types import SupportedTypes

__all__ = ["PydanticNormalizer"]

_T = TypeVar("_T")

# What makes a value read back as it was written: no conversion on reading, no NaN or infinity,
# bytes as base64 rather than as text they may not be, durations in ISO 8601.
_EXACT: Final = ConfigDict(
    strict=True,
    allow_inf_nan=False,
    ser_json_bytes="base64",
    val_json_bytes="base64",
    ser_json_timedelta="iso8601",
)

# Type checkers read an alias only as a statement naming a type written in the code; here the
# type is a value known at run time, which is what TypeAliasType takes there.
_alias_of: Final = cast("Callable[[str, object], object]", TypeAliasType)

# How many types an instance keeps the adapter of. A type expression built per call, such as
# Annotated[int, Field(ge=0)], is a new key each time; the least recently used goes first.
_CACHE_SIZE: Final = 256

# pydantic's words for a value that contains itself: a plain ValueError when dumping, wrapped
# when writing JSON. Its "(depth exceeded)" is a value nested too deep, which is no cycle.
_CYCLE: Final = "Circular reference detected (id repeated)"
_CYCLE_WORDS: Final = frozenset({_CYCLE, f"Error serializing to JSON: ValueError: {_CYCLE}"})


@final
class PydanticNormalizer(NormalizerInterface, DenormalizerInterface):
    """Turns any value pydantic has a schema for into plain data, and plain data back into it.

    Models, dataclasses, typed dicts, enums, dates, decimals, UUIDs, bytes, tuples and sets, and
    containers of them. pydantic does the converting; this maps a call's context onto pydantic's
    options and pydantic's errors onto this package's, with their paths and never their values.
    A validator's message is passed on as the validator worded it: those are the application's
    words, not the data's, so a validator must not quote the value it refuses.

    Each type is read and written under one configuration — strict, finite, bytes as base64,
    durations in ISO 8601 — so a value reads back as it was written. It governs the dataclasses,
    typed dicts and plain types that declare no configuration of their own, except inside a
    model: a model keeps its own ``model_config``, and that configuration, not this one, governs
    what the model holds down to the next type with one of its own. A model that is to be exact
    declares those settings itself. The :data:`~xtr_serializer.STRICT` key overrides strictness
    for every type.

    Data is read as JSON: strict pydantic takes a date or a UUID from a string, a tuple from a
    list, an enum from its value, only in JSON, so the data is handed to it as JSON text. The
    data is what a decoder returns — dicts, lists, strings, numbers, booleans and ``None``; any
    other value is turned into JSON first and so is checked in its JSON form, not as itself.
    Reading an object's attributes (:data:`~xtr_serializer.FROM_ATTRIBUTES`) reads the object
    itself.

    The adapter built for each type is kept, as is the answer that none can be built, for the
    256 types used last; a union's members count in the order written, as pydantic tries them in
    that order. The context is handed to pydantic too, where validators and serializers read it
    as ``info.context``. A call's context wins over the default one.
    """

    def __init__(self, default_context: Context | None = None) -> None:
        """Keep a copy of ``default_context``, so later changes to it are not picked up."""
        self._default_context = dict(default_context or {})
        # Oldest use first: a type used again is moved to the end.
        self._adapters: dict[object, TypeAdapter[object] | str] = {}

    @override
    def normalize(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> NormalizedValue:
        adapter = self._adapter_for(type(data))
        context = {**self._default_context, **(context or {})}
        include, exclude = _names(context, ATTRIBUTES), _names(context, IGNORED_ATTRIBUTES)
        by_alias = _flag(context, BY_ALIAS) is not False
        exclude_none = _flag(context, SKIP_NULL_VALUES) is True
        exclude_unset = _flag(context, SKIP_UNSET_VALUES) is True
        exclude_defaults = _flag(context, SKIP_DEFAULT_VALUES) is True
        try:
            # Dumped in JSON mode, the result holds only what JSON does.
            return cast(
                "NormalizedValue",
                adapter.dump_python(
                    data,
                    mode="json",
                    include=include,
                    exclude=exclude,
                    by_alias=by_alias,
                    exclude_none=exclude_none,
                    exclude_unset=exclude_unset,
                    exclude_defaults=exclude_defaults,
                    warnings="error",  # a value outside its declared type is refused, not written
                    context=context,
                ),
            )
        except ValueError as error:  # pydantic's message quotes the value, so it is not passed on
            cyclic = _is_cycle(error)
        # Raised outside the handler, so no exception holding the data is chained to it.
        if cyclic:
            raise CircularReferenceError("the value contains itself")
        raise NotNormalizableValueError(
            "the value, or one inside it, does not fit its declared type, has no plain form or "
            "is nested too deep",
            current_type=type(data).__qualname__,
        )

    @override
    def supports_normalization(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> bool:
        return not isinstance(self._cached_adapter(type(data)), str)

    @overload
    def denormalize(
        self,
        data: object,
        type_: type[_T],
        format: str | None = None,
        context: Context | None = None,
    ) -> _T: ...

    @overload
    def denormalize(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> object: ...

    @override
    def denormalize(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> object:
        adapter = self._adapter_for(type_)
        context = {**self._default_context, **(context or {})}
        strict, allow_extra = _flag(context, STRICT), _flag(context, ALLOW_EXTRA_ATTRIBUTES)
        extra: Literal["ignore", "forbid"] | None = (
            None if allow_extra is None else "ignore" if allow_extra else "forbid"
        )
        by_alias = _flag(context, BY_ALIAS) is not False
        # pydantic needs one of alias and name to read by; without the alias, it is the name.
        by_name = _flag(context, POPULATE_BY_NAME) if by_alias else True
        from_attributes = _flag(context, FROM_ATTRIBUTES) is True
        collect = _flag(context, COLLECT_DENORMALIZATION_ERRORS) is True
        details: list[ErrorDetails] = []
        text: bytes | None = None
        cyclic = False
        try:
            if from_attributes:
                return adapter.validate_python(
                    data,
                    strict=strict,
                    extra=extra,
                    from_attributes=True,
                    by_alias=by_alias,
                    by_name=by_name,
                    context=context,
                )
            # Infinity written as itself, so that reading refuses it rather than seeing null.
            text = to_json(data, inf_nan_mode="constants")
            return adapter.validate_json(
                text,
                strict=strict,
                extra=extra,
                by_alias=by_alias,
                by_name=by_name,
                context=context,
            )
        except ValidationError as error:
            details = error.errors(include_url=False, include_context=False)
        except ValueError as error:  # data holding what has no JSON form, or holding itself
            cyclic = _is_cycle(error)
        # Located and raised outside the handlers, so no exception holding the data is chained.
        if cyclic:
            raise CircularReferenceError("the data contains itself")
        # Read as JSON, the data is located in the JSON pydantic read, never in the caller's
        # object, whose code could run, or which a generator or a set cannot be indexed into.
        refusals = refusals_of(details, data if text is None else _parsed(text)) if details else []
        if not refusals:
            raise NotNormalizableValueError(
                "the data holds a value that is not plain data, or is nested too deep",
                current_type=type(data).__name__,
            )
        if collect:
            raise PartialDenormalizationError(data, tuple(refusals))
        raise refusals[0]

    @override
    def supports_denormalization(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> bool:
        return not isinstance(self._cached_adapter(type_), str)

    @override
    def get_supported_types(self, format: str | None) -> SupportedTypes:
        # Whether pydantic has a schema for a type depends on the type alone.
        return {"*": True}

    def _adapter_for(self, type_: object) -> TypeAdapter[object]:
        adapter = self._cached_adapter(type_)
        if isinstance(adapter, str):
            raise InvalidArgumentError(adapter)
        return adapter

    def _cached_adapter(self, type_: object) -> TypeAdapter[object] | str:
        """Return the adapter of ``type_``, or why it has none, building it on first use."""
        key = _key_of(type_)
        try:
            _ = hash(key)
        except TypeError:  # a type expression that cannot be hashed is built every time
            return _build_adapter(type_)
        adapter = self._adapters.pop(key, None)
        if adapter is None:
            adapter = _build_adapter(type_)
        self._adapters[key] = adapter
        if len(self._adapters) > _CACHE_SIZE:
            del self._adapters[next(iter(self._adapters))]
        return adapter


def _key_of(type_: object) -> object:
    """Key ``type_`` by its arguments in order, which a union's equality leaves out."""
    arguments: tuple[object, ...] = get_args(type_)
    return (type_, tuple(_key_of(argument) for argument in arguments))


def _build_adapter(type_: object) -> TypeAdapter[object] | str:
    """Build the adapter of ``type_`` under the exact configuration, or say why it has none.

    pydantic refuses a configuration for a bare model, dataclass or typed dict; given one for an
    alias of the type, it applies it to the type and to what the type holds. A type naming what
    is not defined at run time, such as a class imported for type checkers only, gets an adapter
    pydantic finishes on first use; it is finished here, so the name is reported at once.
    """
    name = type_.__qualname__ if isinstance(type_, type) else repr(type_)
    try:
        adapter: TypeAdapter[object] = TypeAdapter(_alias_of("Value", type_), config=_EXACT)
        if not adapter.pydantic_complete:
            _ = adapter.rebuild(raise_errors=True)
    except PydanticSchemaGenerationError:
        return f"pydantic has no schema for {name!r}"
    except PydanticUndefinedAnnotation as error:
        return f"pydantic has no schema for {name!r}: {error.name!r} is not defined"
    return adapter


def _is_cycle(error: ValueError) -> bool:
    """Tell pydantic's refusal of a value that contains itself, which has no type of its own."""
    return str(error) in _CYCLE_WORDS


def _parsed(text: bytes) -> object:
    """Parse the JSON pydantic read, or give ``None`` when it is nested past what parsing takes.

    pydantic reports such JSON as invalid as a whole, at no path, so nothing is lost.
    """
    try:
        return cast("object", from_json(text))
    except ValueError:
        return None


def _flag(context: Context, key: str) -> bool | None:
    """Read an on/off option, ``None`` when it is absent, refusing anything but a bool."""
    value = context.get(key)
    if value is None or isinstance(value, bool):
        return value
    raise InvalidArgumentError(f"{key!r} must be a bool")


def _names(context: Context, key: str) -> set[str] | None:
    """Read a set of field names, ``None`` when it is absent, refusing anything else."""
    value = context.get(key)
    if isinstance(value, AbstractSet) and all(isinstance(name, str) for name in value):
        return cast("set[str]", set(value))
    if value is None:
        return None
    raise InvalidArgumentError(f"{key!r} must be a set of field names")
