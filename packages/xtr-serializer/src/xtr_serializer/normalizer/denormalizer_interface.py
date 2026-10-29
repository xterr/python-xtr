"""What turns plain data back into values of the type asked for."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, TypeVar, overload, runtime_checkable

if TYPE_CHECKING:
    from xtr_serializer.context.context import Context
    from xtr_serializer.supported_types import SupportedTypes

__all__ = ["COLLECT_DENORMALIZATION_ERRORS", "DenormalizerInterface"]

_T = TypeVar("_T")

COLLECT_DENORMALIZATION_ERRORS: Final = "collect_denormalization_errors"
"""The context key asking for every value that does not fit, rather than the first.

On, reading goes on past a value that does not fit its type, then raises one
:class:`~xtr_serializer.exception.PartialDenormalizationError` listing them all instead of a
:class:`~xtr_serializer.exception.NotNormalizableValueError` for the first — so whoever sent the
data can be told everything wrong with it at once, not one field per attempt. Off when absent.
"""


@runtime_checkable
class DenormalizerInterface(Protocol):
    """Turns plain data back into values of the types it handles.

    The last step of deserializing. What it reads came over a wire or out of storage, so it
    checks the data against the type asked for and refuses what does not fit — saying where,
    never repeating the value.
    """

    @overload
    def denormalize(
        self,
        data: object,
        type_: type[_T],
        format: str | None = None,
        context: Context | None = None,
    ) -> _T: ...

    @overload
    def denormalize(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> object: ...

    def denormalize(
        self,
        data: object,
        type_: object,
        format: str | None = None,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
    ) -> object:
        """Return a value of type ``type_`` built from ``data``.

        Args:
            data: The plain data to read, as a decoder returns it.
            type_: The type to build: a class, and the result is typed as an instance of it,
                or any other type expression, such as ``int | None``, and the result is typed
                as ``object``.
            format: The format ``data`` was read from; ``None`` when there is none in view.
            context: Options for this call, :data:`COLLECT_DENORMALIZATION_ERRORS` among them.

        Raises:
            InvalidArgumentError: When ``type_`` is not something this denormalizer builds.
            NotNormalizableValueError: When ``data`` does not fit ``type_``.
            PartialDenormalizationError: When :data:`COLLECT_DENORMALIZATION_ERRORS` is on and
                some values do not fit.
        """
        ...

    def supports_denormalization(
        self,
        data: object,
        type_: object,
        format: str | None = None,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
    ) -> bool:
        """Tell whether :meth:`denormalize` builds ``type_`` from ``data``, read from ``format``."""
        ...

    def get_supported_types(self, format: str | None) -> SupportedTypes:  # noqa: A002 — the name every serializer call uses.
        """Return the types this builds from ``format``, and what its answer for them rests on.

        Lets a serializer pass over this denormalizer for a type it does not build, and remember
        its answer for a type whose answer depends on nothing else, instead of calling
        :meth:`supports_denormalization` for every value.
        """
        ...
