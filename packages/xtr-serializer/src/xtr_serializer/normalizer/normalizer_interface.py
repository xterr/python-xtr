"""What turns values into plain data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_serializer.context.context import Context
    from xtr_serializer.normalized_value import NormalizedValue
    from xtr_serializer.supported_types import SupportedTypes

__all__ = ["NormalizerInterface"]


@runtime_checkable
class NormalizerInterface(Protocol):
    """Turns values of the types it handles into plain data.

    The first step of serializing. A normalizer knows the objects — their fields, the types those
    were declared with — and nothing of the format the plain data is then written in, so the
    same normalizer serves every encoder. A serializer holds several, and gives each value to the
    first that handles it.
    """

    def normalize(
        self,
        data: object,
        format: str | None = None,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
    ) -> NormalizedValue:
        """Return ``data`` as plain data.

        Args:
            data: The value to normalize, one this normalizer handles.
            format: The format the plain data is to be written in, for a normalizer whose
                output depends on it; ``None`` when there is none in view.
            context: Options for this call.

        Raises:
            InvalidArgumentError: When ``data`` is not something this normalizer handles.
            NotNormalizableValueError: When ``data``, or a value inside it, has no exact plain
                form.
            CircularReferenceError: When ``data`` contains itself.
        """
        ...

    def supports_normalization(
        self,
        data: object,
        format: str | None = None,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
    ) -> bool:
        """Tell whether :meth:`normalize` handles ``data``, to be written in ``format``."""
        ...

    def get_supported_types(self, format: str | None) -> SupportedTypes:  # noqa: A002 — the name every serializer call uses.
        """Return the types this handles in ``format``, and what its answer for them rests on.

        Lets a serializer pass over this normalizer for a type it does not handle, and remember
        its answer for a type whose answer depends on nothing else, instead of calling
        :meth:`supports_normalization` for every value.
        """
        ...
