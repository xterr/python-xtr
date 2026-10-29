"""The context builder for the options of the JSON encoder."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_serializer.encoder.json_encoder_keys import JSON_INDENT

if TYPE_CHECKING:
    from xtr_serializer.context.context import Context

__all__ = ["JsonEncoderContextBuilder"]


@final
class JsonEncoderContextBuilder:
    """Builds the options the JSON encoder reads, each under its own key.

    Each method sets one key and touches no other. Immutable: setting an option returns a new
    builder and leaves this one as it was, so a builder holding an application's defaults can be
    extended for one call without that call's options reaching the next.
    """

    __slots__ = ("_context",)

    def __init__(self, context: Context | None = None) -> None:
        """Start from the options in ``context``, or from none.

        Args:
            context: The options to start from — an application's defaults, or what another
                builder built. Copied, so a later change to it does not reach this builder.
        """
        self._context: dict[str, object] = dict(context or {})

    def with_indent(self, indent: int | None) -> JsonEncoderContextBuilder:
        """Return a builder that indents each level by ``indent`` spaces, or by none.

        Sets :data:`~xtr_serializer.JSON_INDENT`; ``None`` writes the value on one line.
        """
        return JsonEncoderContextBuilder({**self._context, JSON_INDENT: indent})

    def to_dict(self) -> dict[str, object]:
        """Return the options built so far, as a new dictionary to pass to a call."""
        return dict(self._context)
