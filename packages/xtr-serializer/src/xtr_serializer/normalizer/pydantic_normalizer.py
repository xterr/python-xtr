"""Values turned into plain data and back by pydantic, under one configuration for exactness."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, TypeVar, cast, final, overload

from pydantic import ValidationError
from pydantic_core import to_json
from typing_extensions import override

from xtr_serializer._type_names import name_of, qualified_name_of
from xtr_serializer.exception import (
    CircularReferenceError,
    InvalidArgumentError,
    NotNormalizableValueError,
    SerializerError,
)
from xtr_serializer.mapping._deferred_refusals import deferring_refusals

from ._adapter_cache import Adapter, AdapterCache
from ._context_options import read_options, write_options
from ._cycles import is_cycle
from ._own_words import own_words
from ._read_back import read_back_refusal
from ._read_refusal import read_refusal
from .denormalizer_interface import DenormalizerInterface
from .normalizer_interface import NormalizerInterface

if TYPE_CHECKING:
    from pydantic_core import ErrorDetails

    from xtr_serializer.context.context import Context
    from xtr_serializer.normalized_value import NormalizedValue
    from xtr_serializer.supported_types import SupportedTypes

__all__ = ["PydanticNormalizer"]

_T = TypeVar("_T")


@final
class PydanticNormalizer(NormalizerInterface, DenormalizerInterface):
    """Turns any value pydantic has a schema for into plain data, and plain data back into it.

    pydantic converts; this maps the context (a call's over the default one, also handed to
    validators as ``info.context``) onto pydantic's options, and pydantic's errors onto this
    package's, with paths and never values. A validator's message is passed on as worded; what
    other code raises as data is read, such as a key of the data comparing itself, is refused
    naming only the class of what it raised. Threads
    may share a normalizer; a type whose comparison waits for another thread, or uses another
    normalizer, can deadlock them.

    Each type is strict, finite, with bytes as base64 and durations in ISO 8601, and a plain
    ``datetime`` in it takes an aware datetime only. A model, or a dataclass pydantic built, keeps
    its own configuration and rules instead, down to the next type with one of its own, wherever
    it sits: a model that is to be exact declares those settings itself, and types its datetimes
    ``AwareDatetime``. The :data:`~xtr_serializer.STRICT` key overrides strictness for every type.

    What is written is checked as the JSON encoder checks it, so a float NaN or infinity a model's
    own configuration allows is refused all the same. It is then read back under the same context
    and refused unless every part comes back equal and of the same type — a decimal NaN, a set,
    tuple or model in a field declaring no type, ``True`` or an enum member in an ``int`` field
    would not; a ``DatePoint`` reads back as the ``datetime`` declared. A partial write is checked
    but not read back. A plain ``datetime`` field keeps the offset of a zone but not its name;
    :data:`~xtr_serializer.ZonedDateTime` keeps both. Data is read as JSON, which is where strict
    pydantic takes a date, a UUID, a tuple or an enum from text or a list.

    A value of a class hierarchy (see :func:`~xtr_serializer.discriminator_map`) is written with
    its class's name and read back as that class, wherever its base or a class under it is
    declared.

    A value is written as the type it is declared with, when one is given, and as its own class
    otherwise. A list or a dict on its own declares nothing about what it holds, so it is written
    only when all it holds reads back as itself — plain JSON — unless its type is declared, such
    as ``list[Item]``; a value of a class no schema is built for, by the annotation it is declared
    with, such as one carrying pydantic's ``PlainSerializer`` and ``PlainValidator``.

    The bytes in a named tuple inside a typed dict with a configuration of its own — and, before
    pydantic 2.14, inside a model or a dataclass with one — are written as base64 whatever that
    configuration says, yet read as it says: unless it says base64 too, a value holding them
    would read back changed, so it is refused.
    """

    def __init__(self, default_context: Context | None = None) -> None:
        """Keep a copy of ``default_context``, so later changes to it are not picked up."""
        self._default_context = dict(default_context or {})
        self._adapters = AdapterCache()

    @override
    def normalize(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> NormalizedValue:
        adapter = self._adapter_for(type(data) if type_ is None else type_)
        context = {**self._default_context, **(context or {})}
        options = write_options(context)
        written: NormalizedValue = None
        failure: ValueError | None = None
        with deferring_refusals() as deferred:
            try:
                # Dumped in JSON mode, the result holds only what JSON does.
                written = cast(
                    "NormalizedValue",
                    adapter.writer.dump_python(
                        data,
                        mode="json",
                        include=options.include,
                        exclude=options.exclude,
                        by_alias=options.by_alias,
                        exclude_none=options.exclude_none,
                        exclude_unset=options.exclude_unset,
                        exclude_defaults=options.exclude_defaults,
                        warnings="error",  # a value outside its declared type is refused
                        context=context,
                    ),
                )
            except ValueError as error:  # pydantic's message quotes the value: not passed on
                failure = error
        # Met first, a refusal kept inside a class hierarchy's value is what made the rest fail.
        failure = deferred[0] if deferred else failure
        refusal: SerializerError | None = None
        cyclic = False
        if failure is not None:
            refusal = own_words(failure)
            cyclic = is_cycle(failure)
        else:
            refusal = read_back_refusal(
                data,
                written,
                None
                if options.partial
                else partial(
                    adapter.reader.validate_json,
                    by_alias=options.by_alias,
                    by_name=None if options.by_alias else True,
                    context=context,
                ),
                by_alias=options.by_alias,
            )
            if refusal is None:
                return written
        # Raised outside the handler, so no exception holding the data is chained to it.
        if refusal is not None:
            raise refusal from None
        if cyclic:
            raise CircularReferenceError("the value contains itself")
        raise NotNormalizableValueError(
            "the value, or one inside it, does not fit its declared type, has no plain form or "
            "is nested too deep",
            current_type=qualified_name_of(type(data)),
        )

    @override
    def supports_normalization(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> bool:
        return not isinstance(self._adapters.get(type(data) if type_ is None else type_), str)

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
        options = read_options(context)
        details: list[ErrorDetails] = []
        text: bytes | None = None
        cyclic = False
        raised = ""
        try:
            if options.from_attributes:
                return cast(
                    "object",
                    adapter.reader.validate_python(
                        data,
                        strict=options.strict,
                        extra=options.extra,
                        from_attributes=True,
                        by_alias=options.by_alias,
                        by_name=options.by_name,
                        context=context,
                    ),
                )
            # Infinity written as itself, so that reading refuses it rather than seeing null.
            text = to_json(data, inf_nan_mode="constants")
            return cast(
                "object",
                adapter.reader.validate_json(
                    text,
                    strict=options.strict,
                    extra=options.extra,
                    by_alias=options.by_alias,
                    by_name=options.by_name,
                    context=context,
                ),
            )
        except ValidationError as error:
            details = error.errors(include_url=False)
        except ValueError as error:  # data holding what has no JSON form, or holding itself
            cyclic = is_cycle(error)
        except SerializerError:
            raise
        except Exception as error:  # noqa: BLE001 - what the data's or a validator's code raises
            # Its message may quote the data, such as a key's comparison saying what it holds.
            raised = name_of(type(error))
        # Located and raised outside the handlers, so no exception holding the data is chained.
        if cyclic:
            raise CircularReferenceError("the data contains itself")
        if raised:
            raise NotNormalizableValueError(
                f"reading the data raised {raised}",
                current_type=name_of(type(data)),
                error_type="not_readable",
            )
        raise read_refusal(data, details, text, collect=options.collect)

    @override
    def supports_denormalization(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> bool:
        return not isinstance(self._adapters.get(type_), str)

    @override
    def get_supported_types(self, format: str | None) -> SupportedTypes:
        # Whether pydantic has a schema for a type depends on the type alone.
        return {"*": True}

    def _adapter_for(self, type_: object) -> Adapter:
        adapter = self._adapters.get(type_)
        if isinstance(adapter, str):
            raise InvalidArgumentError(adapter)
        return adapter
