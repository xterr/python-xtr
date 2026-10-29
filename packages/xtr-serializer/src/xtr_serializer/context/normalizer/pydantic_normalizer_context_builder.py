"""The context builder for the options of the pydantic normalizer."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_serializer.context._context_builder_trait import ContextBuilderTrait
from xtr_serializer.normalizer.pydantic_normalizer_keys import (
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
    from collections.abc import Set as AbstractSet

__all__ = ["PydanticNormalizerContextBuilder"]


@final
class PydanticNormalizerContextBuilder(ContextBuilderTrait):
    """Builds the options the pydantic normalizer reads, each under its own key.

    Each method sets one key and touches no other, so the options of the other steps can be put
    in the context it starts from. Immutable: setting an option returns a new builder and leaves
    this one as it was, so a builder holding an application's defaults can be extended for one
    call without that call's options reaching the next. Nothing a caller does to the plain
    dictionaries, lists, tuples and sets of the context it starts from, or of the one it returns,
    reaches it; any other value is handed on as it is.

    ```python
    context = (
        PydanticNormalizerContextBuilder()
        .with_ignored_attributes({"password_hash"})
        .with_skip_null_values(True)
        .to_dict()
    )
    ```
    """

    __slots__ = ()

    def with_attributes(self, attributes: AbstractSet[str]) -> PydanticNormalizerContextBuilder:
        """Return a builder that writes only the fields named in ``attributes``.

        Sets :data:`~xtr_serializer.ATTRIBUTES`, to the names as they are now.
        """
        return self._with(ATTRIBUTES, frozenset(attributes))

    def with_ignored_attributes(
        self,
        ignored_attributes: AbstractSet[str],
    ) -> PydanticNormalizerContextBuilder:
        """Return a builder that never writes the fields named in ``ignored_attributes``.

        Sets :data:`~xtr_serializer.IGNORED_ATTRIBUTES`, to the names as they are now.
        """
        return self._with(IGNORED_ATTRIBUTES, frozenset(ignored_attributes))

    def with_skip_null_values(self, skip_null_values: bool) -> PydanticNormalizerContextBuilder:
        """Return a builder that sets whether fields holding ``None`` are left out.

        Sets :data:`~xtr_serializer.SKIP_NULL_VALUES`.
        """
        return self._with(SKIP_NULL_VALUES, skip_null_values)

    def with_skip_unset_values(self, skip_unset_values: bool) -> PydanticNormalizerContextBuilder:
        """Return a builder that sets whether fields never given a value are left out.

        Sets :data:`~xtr_serializer.SKIP_UNSET_VALUES`.
        """
        return self._with(SKIP_UNSET_VALUES, skip_unset_values)

    def with_skip_default_values(
        self,
        skip_default_values: bool,
    ) -> PydanticNormalizerContextBuilder:
        """Return a builder that sets whether fields holding their default are left out.

        Sets :data:`~xtr_serializer.SKIP_DEFAULT_VALUES`.
        """
        return self._with(SKIP_DEFAULT_VALUES, skip_default_values)

    def with_by_alias(self, by_alias: bool) -> PydanticNormalizerContextBuilder:
        """Return a builder that sets whether fields are written and read under their alias.

        Sets :data:`~xtr_serializer.BY_ALIAS`.
        """
        return self._with(BY_ALIAS, by_alias)

    def with_strict(self, strict: bool) -> PydanticNormalizerContextBuilder:
        """Return a builder that sets whether reading refuses data it would have to convert.

        Sets :data:`~xtr_serializer.STRICT`.
        """
        return self._with(STRICT, strict)

    def with_allow_extra_attributes(
        self,
        allow_extra_attributes: bool,
    ) -> PydanticNormalizerContextBuilder:
        """Return a builder that sets whether data may carry fields its type does not declare.

        Sets :data:`~xtr_serializer.ALLOW_EXTRA_ATTRIBUTES`.
        """
        return self._with(ALLOW_EXTRA_ATTRIBUTES, allow_extra_attributes)

    def with_from_attributes(self, from_attributes: bool) -> PydanticNormalizerContextBuilder:
        """Return a builder that sets whether an object is read through its attributes.

        Sets :data:`~xtr_serializer.FROM_ATTRIBUTES`.
        """
        return self._with(FROM_ATTRIBUTES, from_attributes)

    def with_populate_by_name(self, populate_by_name: bool) -> PydanticNormalizerContextBuilder:
        """Return a builder that sets whether a field is read under its name as well as its alias.

        Sets :data:`~xtr_serializer.POPULATE_BY_NAME`.
        """
        return self._with(POPULATE_BY_NAME, populate_by_name)
