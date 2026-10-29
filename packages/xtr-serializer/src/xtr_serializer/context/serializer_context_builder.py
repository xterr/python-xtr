"""The context builder for the options of the serializer as a whole."""

from __future__ import annotations

from typing import final

from xtr_serializer.normalizer.denormalizer_interface import COLLECT_DENORMALIZATION_ERRORS

from ._context_builder_trait import ContextBuilderTrait

__all__ = ["SerializerContextBuilder"]


@final
class SerializerContextBuilder(ContextBuilderTrait):
    """Builds the options that concern a whole call rather than one normalizer or encoder.

    Immutable: setting an option returns a new builder and leaves this one as it was, so a
    builder holding an application's defaults can be extended for one call without that call's
    options reaching the next. Nothing a caller does to the plain dictionaries, lists, tuples and
    sets of the context it starts from, or of the one it returns, reaches it; any other value is
    handed on as it is.
    """

    __slots__ = ()

    def with_collect_denormalization_errors(
        self,
        collect_denormalization_errors: bool,
    ) -> SerializerContextBuilder:
        """Return a builder that sets whether reading reports every value that does not fit.

        Sets :data:`~xtr_serializer.COLLECT_DENORMALIZATION_ERRORS`.
        """
        return self._with(COLLECT_DENORMALIZATION_ERRORS, collect_denormalization_errors)
