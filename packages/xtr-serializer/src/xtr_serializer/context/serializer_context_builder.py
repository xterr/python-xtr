"""The context builder for the options of the serializer as a whole."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_serializer.normalizer.denormalizer_interface import COLLECT_DENORMALIZATION_ERRORS

if TYPE_CHECKING:
    from .context import Context

__all__ = ["SerializerContextBuilder"]


@final
class SerializerContextBuilder:
    """Builds the options that concern a whole call rather than one normalizer or encoder.

    Immutable: setting an option returns a new builder and leaves this one as it was, so a
    builder holding an application's defaults can be extended for one call without that call's
    options reaching the next.
    """

    __slots__ = ("_context",)

    def __init__(self, context: Context | None = None) -> None:
        """Start from the options in ``context``, or from none.

        Args:
            context: The options to start from — an application's defaults, or what another
                builder built. Copied, so a later change to it does not reach this builder.
        """
        self._context: dict[str, object] = dict(context or {})

    def with_collect_denormalization_errors(
        self,
        collect_denormalization_errors: bool,
    ) -> SerializerContextBuilder:
        """Return a builder that sets whether reading reports every value that does not fit.

        Sets :data:`~xtr_serializer.COLLECT_DENORMALIZATION_ERRORS`.
        """
        return SerializerContextBuilder(
            {**self._context, COLLECT_DENORMALIZATION_ERRORS: collect_denormalization_errors},
        )

    def to_dict(self) -> dict[str, object]:
        """Return the options built so far, as a new dictionary to pass to a call."""
        return dict(self._context)
