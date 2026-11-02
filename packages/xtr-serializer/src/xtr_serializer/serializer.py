"""Values written as text through a chain of normalizers and encoders, and read back."""

from __future__ import annotations

from types import NoneType
from typing import TYPE_CHECKING, Final, TypeVar, cast, final, overload

from typing_extensions import override

from ._dispatch import Dispatch
from ._type_names import qualified_name_of
from ._written_types import written_name_of
from .encoder._encoder_chain import EncoderChain
from .encoder.decoder_interface import DecoderInterface
from .encoder.encoder_interface import EncoderInterface
from .exception import InvalidArgumentError, NotNormalizableValueError
from .normalizer.denormalizer_aware_interface import DenormalizerAwareInterface
from .normalizer.denormalizer_interface import DenormalizerInterface
from .normalizer.normalizer_aware_interface import NormalizerAwareInterface
from .normalizer.normalizer_interface import NormalizerInterface
from .serializer_aware_interface import SerializerAwareInterface
from .serializer_interface import SerializerInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .context.context import Context
    from .normalized_value import NormalizedValue
    from .supported_types import SupportedTypes

__all__ = ["Serializer"]

_T = TypeVar("_T")

# The values that are plain data as they are: their exact classes, so that an enum member that
# is a string, say, is still handed to a normalizer.
_PRIMITIVES: Final = frozenset({NoneType, bool, int, float, str})


@final
class Serializer(
    SerializerInterface,
    NormalizerInterface,
    DenormalizerInterface,
    EncoderInterface,
    DecoderInterface,
):
    """Writes values as text, and reads text back, through the normalizers and encoders it holds.

    Serializing normalizes the value, then encodes the plain data; deserializing decodes the text,
    then denormalizes the data into the type asked for. Each step goes to the first normalizer or
    encoder, in the order given, that handles it. The serializer hands itself to each that asks,
    through ``set_serializer``, ``set_normalizer`` or ``set_denormalizer``, for nested values.

    A call's context wins over the default one key by key. A format nothing encodes is refused
    before anything is normalized. ``None``, booleans, integers, floats and strings are written as
    they are, unless a type is declared for them. A list or a dict is not looked into: it goes to
    a normalizer like any value, and the pydantic normalizer writes it only when it holds plain
    JSON or its type is declared (``type_``). Which normalizer handles a type is remembered as its
    ``get_supported_types`` allows. Threads may share a serializer.
    """

    __slots__ = ("_default_context", "_denormalizers", "_encoders", "_normalizers")

    def __init__(
        self,
        normalizers: Sequence[NormalizerInterface | DenormalizerInterface] = (),
        encoders: Sequence[EncoderInterface | DecoderInterface] = (),
        default_context: Context | None = None,
    ) -> None:
        """Hold ``normalizers`` and ``encoders``, each in priority order, and hand itself to them.

        Raises:
            InvalidArgumentError: When a normalizer neither normalizes nor denormalizes, or an
                encoder neither encodes nor decodes.
        """
        for normalizer in normalizers:
            # Checked all the same: a serializer built from configuration is handed what it says.
            if not isinstance(normalizer, (NormalizerInterface, DenormalizerInterface)):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise InvalidArgumentError(
                    f"{qualified_name_of(type(normalizer))!r} neither normalizes nor denormalizes"
                )
        self._encoders = EncoderChain(encoders)
        self._default_context = dict(default_context or {})
        self._normalizers = Dispatch(
            [one for one in normalizers if isinstance(one, NormalizerInterface)]
        )
        self._denormalizers = Dispatch(
            [one for one in normalizers if isinstance(one, DenormalizerInterface)]
        )
        for one in (*normalizers, *encoders):
            if isinstance(one, SerializerAwareInterface):
                one.set_serializer(self)
            if isinstance(one, NormalizerAwareInterface):
                one.set_normalizer(self)
            if isinstance(one, DenormalizerAwareInterface):
                one.set_denormalizer(self)

    @override
    def serialize(
        self,
        data: object,
        format: str,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> str:
        encoder = self._encoders.encoder_for(format)
        context = self._merged(context)
        return encoder.encode(self._normalize(data, format, context, type_), format, context)

    @overload
    def deserialize(
        self,
        data: str | bytes,
        type_: type[_T],
        format: str,
        context: Context | None = None,
    ) -> _T: ...

    @overload
    def deserialize(
        self,
        data: str | bytes,
        type_: object,
        format: str,
        context: Context | None = None,
    ) -> object: ...

    @override
    def deserialize(
        self,
        data: str | bytes,
        type_: object,
        format: str,
        context: Context | None = None,
    ) -> object:
        decoder = self._encoders.decoder_for(format)
        context = self._merged(context)
        return self._denormalize(decoder.decode(data, format, context), type_, format, context)

    @override
    def normalize(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> NormalizedValue:
        return self._normalize(data, format, self._merged(context), type_)

    @override
    def supports_normalization(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> bool:
        if type_ is None and type(data) in _PRIMITIVES:
            return True
        return self._normalizer_for(data, format, self._merged(context), type_) is not None

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
        return self._denormalize(data, type_, format, self._merged(context))

    @override
    def supports_denormalization(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> bool:
        context = self._merged(context)
        found = self._denormalizers.first(
            type_, format, lambda one: one.supports_denormalization(data, type_, format, context)
        )
        return found is not None

    @override
    def get_supported_types(self, format: str | None) -> SupportedTypes:
        # Whether a normalizer it holds handles a value may rest on the value.
        return {"*": False}

    @override
    def encode(self, data: NormalizedValue, format: str, context: Context | None = None) -> str:
        return self._encoders.encoder_for(format).encode(data, format, self._merged(context))

    @override
    def supports_encoding(self, format: str) -> bool:
        return self._encoders.encodes(format)

    @override
    def decode(
        self, data: str | bytes, format: str, context: Context | None = None
    ) -> NormalizedValue:
        return self._encoders.decoder_for(format).decode(data, format, self._merged(context))

    @override
    def supports_decoding(self, format: str) -> bool:
        return self._encoders.decodes(format)

    def _merged(self, context: Context | None) -> Context:
        """Give ``context`` over the default one, which it wins key by key."""
        return {**self._default_context, **context} if context else self._default_context

    def _normalize(
        self,
        data: object,
        format: str | None,  # noqa: A002 — the name every serializer call uses.
        context: Context,
        type_: object,
    ) -> NormalizedValue:
        """Normalize ``data``, declared as ``type_``, under the merged ``context``."""
        if type_ is None and type(data) in _PRIMITIVES:
            return cast("NormalizedValue", data)
        normalizer = self._normalizer_for(data, format, context, type_)
        if normalizer is None:
            raise NotNormalizableValueError(
                "no normalizer handles it", current_type=qualified_name_of(type(data))
            )
        return normalizer.normalize(data, format, context, type_=type_)

    def _denormalize(
        self,
        data: object,
        type_: object,
        format: str | None,  # noqa: A002 — the name every serializer call uses.
        context: Context,
    ) -> object:
        """Denormalize ``data`` into ``type_`` under the merged ``context``."""
        denormalizer = self._denormalizers.first(
            type_, format, lambda one: one.supports_denormalization(data, type_, format, context)
        )
        if denormalizer is None:
            raise NotNormalizableValueError(
                "no denormalizer reads into it",
                expected_types=(written_name_of(type_),),
                error_type="unsupported",
            )
        return denormalizer.denormalize(data, type_, format, context)

    def _normalizer_for(
        self,
        data: object,
        format: str | None,  # noqa: A002 — the name every serializer call uses.
        context: Context,
        type_: object,
    ) -> NormalizerInterface | None:
        """Give the first normalizer handling ``data``, declared as ``type_``, if any."""
        return self._normalizers.first(
            type(data) if type_ is None else type_,
            format,
            lambda one: one.supports_normalization(data, format, context, type_=type_),
        )
