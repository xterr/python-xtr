"""The context builder for the options of the JSON encoder."""

from __future__ import annotations

from typing import final

from xtr_serializer.context._context_builder_trait import ContextBuilderTrait
from xtr_serializer.encoder.json_encoder_keys import JSON_INDENT

__all__ = ["JsonEncoderContextBuilder"]


@final
class JsonEncoderContextBuilder(ContextBuilderTrait):
    """Builds the options the JSON encoder reads, each under its own key.

    Each method sets one key and touches no other. Immutable: setting an option returns a new
    builder and leaves this one as it was, so a builder holding an application's defaults can be
    extended for one call without that call's options reaching the next. Nothing a caller does
    to the plain dictionaries, lists, tuples and sets of the context it starts from, or of the
    one it returns, reaches it; any other value is handed on as it is.
    """

    __slots__ = ()

    def with_indent(self, indent: int | None) -> JsonEncoderContextBuilder:
        """Return a builder that indents each level by ``indent`` spaces, or by none.

        Sets :data:`~xtr_serializer.JSON_INDENT`; ``None`` writes the value on one line.
        """
        return self._with(JSON_INDENT, indent)
