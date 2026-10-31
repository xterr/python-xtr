"""The encoders and decoders a serializer holds, each format going to the first that handles it."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import InvalidArgumentError, UnsupportedFormatError

from .decoder_interface import DecoderInterface
from .encoder_interface import EncoderInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["EncoderChain"]


@final
class EncoderChain:
    """Finds the first encoder, or decoder, in the order given, that handles a format."""

    __slots__ = ("_decoders", "_encoders")

    def __init__(self, encoders: Sequence[EncoderInterface | DecoderInterface]) -> None:
        """Hold the encoders and the decoders among ``encoders``, in their order.

        Raises:
            InvalidArgumentError: When one neither encodes nor decodes.
        """
        for encoder in encoders:
            # Checked all the same: a serializer built from configuration is handed what it says.
            if not isinstance(encoder, (EncoderInterface, DecoderInterface)):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise InvalidArgumentError(
                    f"{qualified_name_of(type(encoder))!r} neither encodes nor decodes"
                )
        self._encoders = tuple(one for one in encoders if isinstance(one, EncoderInterface))
        self._decoders = tuple(one for one in encoders if isinstance(one, DecoderInterface))

    def encodes(self, format: str) -> bool:  # noqa: A002 — the name every serializer call uses.
        """Tell whether one of the encoders writes ``format``."""
        return any(encoder.supports_encoding(format) for encoder in self._encoders)

    def decodes(self, format: str) -> bool:  # noqa: A002 — the name every serializer call uses.
        """Tell whether one of the decoders reads ``format``."""
        return any(decoder.supports_decoding(format) for decoder in self._decoders)

    def encoder_for(self, format: str) -> EncoderInterface:  # noqa: A002 — the name every serializer call uses.
        """Give the first encoder writing ``format``.

        Raises:
            UnsupportedFormatError: When none does.
        """
        for encoder in self._encoders:
            if encoder.supports_encoding(format):
                return encoder
        raise UnsupportedFormatError(format)

    def decoder_for(self, format: str) -> DecoderInterface:  # noqa: A002 — the name every serializer call uses.
        """Give the first decoder reading ``format``.

        Raises:
            UnsupportedFormatError: When none does.
        """
        for decoder in self._decoders:
            if decoder.supports_decoding(format):
                return decoder
        raise UnsupportedFormatError(format)
