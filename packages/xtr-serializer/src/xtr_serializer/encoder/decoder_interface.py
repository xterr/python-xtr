"""What reads text in a format back into plain data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_serializer.context.context import Context
    from xtr_serializer.normalized_value import NormalizedValue

__all__ = ["DecoderInterface"]


@runtime_checkable
class DecoderInterface(Protocol):
    """Reads text in the formats it supports back into plain data.

    The first step of deserializing. A decoder checks only that the text is valid in its format;
    whether the data fits the type asked for is for the denormalizer to say, so one decoder
    serves every type.
    """

    def decode(
        self,
        data: str | bytes,
        format: str,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
    ) -> NormalizedValue:
        """Return the plain data ``data`` holds.

        Args:
            data: Text in ``format``, as a string or as the bytes it arrived in.
            format: The format ``data`` is in, one this decoder supports.
            context: Options for this call.

        Raises:
            NotEncodableValueError: When ``data`` is not valid in ``format``.
        """
        ...

    def supports_decoding(self, format: str) -> bool:  # noqa: A002 — the name every serializer call uses.
        """Tell whether this reads ``format``."""
        ...
