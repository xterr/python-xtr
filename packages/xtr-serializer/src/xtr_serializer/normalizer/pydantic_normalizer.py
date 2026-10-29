"""Values turned into plain data and back by pydantic, under one configuration for exactness."""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Final, Literal, TypeVar, cast, final, overload

from pydantic import ConfigDict, TypeAdapter, ValidationError
from pydantic.errors import PydanticSchemaGenerationError, PydanticUndefinedAnnotation
from pydantic_core import to_json
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


@final
class PydanticNormalizer(NormalizerInterface, DenormalizerInterface):
    """Turns any value pydantic has a schema for into plain data, and plain data back into it.

    Models, dataclasses, typed dicts, enums, dates, decimals, UUIDs, bytes, tuples and sets, and
    containers of them. pydantic does the converting; this maps a call's context onto pydantic's
    options and pydantic's errors onto this package's, with their paths and never their values.

    Each type is read and written under one configuration — strict, finite, bytes as base64,
    durations in ISO 8601 — so a value reads back as it was written. It governs every dataclass,
    typed dict and plain type, nested ones included. A model keeps its own ``model_config``:
    pydantic gives a model no configuration but its own, so a model that is to be exact declares
    those settings itself. The :data:`~xtr_serializer.STRICT` key overrides strictness for both.

    Data is read as JSON: strict pydantic takes a date or a UUID from a string, a tuple from a
    list, an enum from its value, only in JSON, so the data is handed to it as JSON text. Reading
    an object's attributes (:data:`~xtr_serializer.FROM_ATTRIBUTES`) reads the object itself.

    The adapter built for each type is kept, as is the answer that none can be built. The context
    is handed to pydantic too, where validators and serializers read it as ``info.context``. A
    call's context wins over the default one.
    """

    __slots__ = ("_adapters", "_default_context")

    def __init__(self, default_context: Context | None = None) -> None:
        """Keep a copy of ``default_context``, so later changes to it are not picked up."""
        self._default_context = dict(default_context or {})
        self._adapters: dict[object, TypeAdapter[object] | None] = {}

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
            "the value, or one inside it, does not fit its declared type or has no plain form",
            current_type=type(data).__qualname__,
        )

    @override
    def supports_normalization(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> bool:
        return self._cached_adapter(type(data)) is not None

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
        refusals: list[NotNormalizableValueError] = []
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
            refusals = refusals_of(error.errors(include_url=False, include_context=False))
        except ValueError as error:  # data holding what has no JSON form, or holding itself
            cyclic = _is_cycle(error)
        if cyclic:
            raise CircularReferenceError("the data contains itself")
        if not refusals:
            raise NotNormalizableValueError(
                "the data holds a value that is not plain data", current_type=type(data).__name__
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
        return self._cached_adapter(type_) is not None

    @override
    def get_supported_types(self, format: str | None) -> SupportedTypes:
        # Whether pydantic has a schema for a type depends on the type alone.
        return {"*": True}

    def _adapter_for(self, type_: object) -> TypeAdapter[object]:
        adapter = self._cached_adapter(type_)
        if adapter is None:
            name = type_.__qualname__ if isinstance(type_, type) else repr(type_)
            raise InvalidArgumentError(f"pydantic has no schema for {name!r}")
        return adapter

    def _cached_adapter(self, type_: object) -> TypeAdapter[object] | None:
        try:
            cached = type_ in self._adapters
        except TypeError:  # a type expression that cannot be hashed is built every time
            return _build_adapter(type_)
        if not cached:
            self._adapters[type_] = _build_adapter(type_)
        return self._adapters[type_]


def _build_adapter(type_: object) -> TypeAdapter[object] | None:
    """Build the adapter of ``type_`` under the exact configuration, or ``None`` if it has none.

    pydantic refuses a configuration for a bare model, dataclass or typed dict; given one for an
    alias of the type, it applies it to the type and to what the type holds.
    """
    try:
        return TypeAdapter(_alias_of("Value", type_), config=_EXACT)
    except (PydanticSchemaGenerationError, PydanticUndefinedAnnotation):
        return None


def _is_cycle(error: ValueError) -> bool:
    """Tell pydantic's refusal of a value that contains itself; it has no type of its own."""
    return "Circular reference" in str(error)


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
