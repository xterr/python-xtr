"""What writes plain data as text in a format."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_serializer.context.context import Context
    from xtr_serializer.normalized_value import NormalizedValue

__all__ = ["EncoderInterface"]


@runtime_checkable
class EncoderInterface(Protocol):
    """Writes plain data as text in the formats it supports.

    The second step of serializing. An encoder is only ever handed plain data, so it knows its
    format and no class at all, and one encoder serves every type.
    """

    def encode(
        self,
        data: NormalizedValue,
        format: str,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
    ) -> str:
        """Return ``data`` written as text in ``format``.

        Args:
            data: The plain data to write, as a normalizer returns it.
            format: The format to write it in, one this encoder supports.
            context: Options for this call.

        Raises:
            NotEncodableValueError: When ``data`` has no exact form in ``format``.
        """
        ...

    def supports_encoding(self, format: str) -> bool:  # noqa: A002 — the name every serializer call uses.
        """Tell whether this writes ``format``."""
        ...
