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
    same normalizer serves every encoder. A serializer holds a list of them, and gives each value
    to the first that handles it.
    """

    def normalize(
        self,
        data: object,
        format: str | None = None,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> NormalizedValue:
        """Return ``data`` as plain data.

        What is written, and how it reads back, follows from a type: the one ``data`` was
        declared with when one is given, its own class otherwise. A list or a dict declares
        nothing about what it holds, nor does a value of a class hierarchy about its base; the
        declared type does, so that what reads it back as that type gets back what was written.

        Args:
            data: The value to normalize, one this normalizer handles.
            format: The format the plain data is to be written in, for a normalizer whose
                output depends on it; ``None`` when there is none in view.
            context: Options for this call.
            type_: The type ``data`` was declared with, such as ``list[Item]``; ``None`` for its
                own class.

        Raises:
            InvalidArgumentError: When ``data``, or ``type_``, is not something this normalizer
                handles.
            NotNormalizableValueError: When ``data``, or a value inside it, has no exact plain
                form, or does not fit ``type_`` — and, from a serializer holding several
                normalizers, when none of them handles it.
            CircularReferenceError: When ``data`` contains itself.
        """
        ...

    def supports_normalization(
        self,
        data: object,
        format: str | None = None,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> bool:
        """Tell whether :meth:`normalize` handles ``data``, declared as ``type_``, in ``format``."""
        ...

    def get_supported_types(self, format: str | None) -> SupportedTypes:  # noqa: A002 — the name every serializer call uses.
        """Return the types this handles in ``format``, and what its answer for them rests on.

        Lets a serializer pass over this normalizer for a type it does not handle, and remember
        its answer for a type whose answer depends on nothing else, instead of calling
        :meth:`supports_normalization` for every value.
        """
        ...
