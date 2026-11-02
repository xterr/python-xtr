"""What writes values as text and reads text back into the type asked for."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, overload, runtime_checkable

if TYPE_CHECKING:
    from xtr_serializer.context.context import Context

__all__ = ["SerializerInterface"]

_T = TypeVar("_T")


@runtime_checkable
class SerializerInterface(Protocol):
    """Writes a value as text in a format, and reads such text back into the type asked for.

    What an application depends on to put values on a wire or in storage and take them back.
    Behind it, a normalizer turns the value into plain data and an encoder writes that data in
    the format; reading takes the same steps the other way. What is read back equals what was
    written: a value that could not make the round trip exactly is refused when it is written,
    rather than changed.
    """

    def serialize(
        self,
        data: object,
        format: str,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> str:
        """Return ``data`` written as text in ``format``.

        What is written follows from the type ``data`` is declared with, its own class unless
        ``type_`` says otherwise; reading the text back into that same type gives back ``data``.

        Args:
            data: The value to write.
            format: The format to write it in, such as ``"json"``.
            context: Options for this call, each read by the step it concerns.
            type_: The type ``data`` is declared with, the one it is to be read back into: a
                list or a dict declares nothing about what it holds, ``list[Item]`` does; and the
                base of a class hierarchy may be declared for a value of a class under it.
                ``None`` for its own class.

        Raises:
            UnsupportedFormatError: When nothing writes ``format``.
            NotNormalizableValueError: When ``data``, or a value inside it, has no exact plain
                form, or does not fit ``type_``.
            CircularReferenceError: When ``data`` contains itself.
            NotEncodableValueError: When the plain data has no exact form in ``format``.
        """
        ...

    @overload
    def deserialize(
        self,
        data: str | bytes,
        type_: type[_T],
        format: str,
        context: Context | None = None,
    ) -> _T: ...

    @overload
    def deserialize(
        self,
        data: str | bytes,
        type_: object,
        format: str,
        context: Context | None = None,
    ) -> object: ...

    def deserialize(
        self,
        data: str | bytes,
        type_: object,
        format: str,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
    ) -> object:
        """Return the value of type ``type_`` that ``data``, text in ``format``, holds.

        Args:
            data: Text in ``format``, as a string or as the bytes it arrived in.
            type_: The type to read into: a class, and the result is typed as an instance of
                it, or any other type expression, such as ``int | None``, and the result is
                typed as ``object``.
            format: The format ``data`` is in, such as ``"json"``.
            context: Options for this call, each read by the step it concerns.

        Raises:
            UnsupportedFormatError: When nothing reads ``format``.
            NotEncodableValueError: When ``data`` is not valid in ``format``.
            NotNormalizableValueError: When what ``data`` holds does not fit ``type_``.
            PartialDenormalizationError: When the context asks for every error at once and
                some values do not fit.
        """
        ...
