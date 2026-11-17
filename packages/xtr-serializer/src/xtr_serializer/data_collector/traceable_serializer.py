"""A serializer that records, for the profiled request, every call made on it."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final, NamedTuple, final, overload

from xtr_clock import MonotonicClock

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer._written_types import written_name_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_clock import ClockInterface, DatePoint
    from xtr_http_kernel.data_collector import RequestTrace

    from xtr_serializer.context.context import Context
    from xtr_serializer.normalized_value import NormalizedValue
    from xtr_serializer.serializer import Serializer
    from xtr_serializer.supported_types import SupportedTypes

    from .serializer_call import SerializerCall

__all__ = ["TraceableSerializer"]

_MILLISECOND: Final = timedelta(milliseconds=1)


class _Call(NamedTuple):
    """What names a call: the method, the value's class, the format, the context, the type asked."""

    method: str
    data: object
    format: str | None
    context: Context | None
    # ``(type_,)`` for a call reading into a type; empty for one that does not.
    target: tuple[object, ...] = ()


@final
class TraceableSerializer:
    """Hands every call to a serializer, and records it for the request being profiled.

    It is every interface the serializer is — ``SerializerInterface``, ``NormalizerInterface``,
    ``DenormalizerInterface``, ``EncoderInterface`` and ``DecoderInterface`` — so whatever asks
    for one gets this and nothing else changes. It implements them without subclassing them: a
    class subclassing a normalizer or an encoder interface is collected into a serializer by the
    container, and this one wraps a serializer rather than joining one.

    Each call of :meth:`serialize`, :meth:`deserialize`, :meth:`normalize`, :meth:`denormalize`,
    :meth:`encode` and :meth:`decode` is recorded as a
    :class:`~xtr_serializer.data_collector.SerializerCall` — how long it took, and what it raised,
    which is raised on unchanged. The ``supports_*`` questions and :meth:`get_supported_types`
    are answered unrecorded: they ask, they do no work.

    Only the calls made on this serializer are recorded. A normalizer writing a nested value goes
    through the serializer it was handed when it was built — the wrapped one — so a
    ``serialize`` is one entry, whatever it normalizes on the way.

    Outside a profiled request a call goes straight through, unrecorded and untimed.
    """

    __slots__ = ("_clock", "_name", "_serializer", "_trace")

    def __init__(
        self,
        serializer: Serializer,
        name: str,
        trace: RequestTrace[SerializerCall],
        *,
        clock: ClockInterface | None = None,
    ) -> None:
        """Record each call on ``serializer``, under ``name``, into ``trace``.

        ``clock`` times the calls; a monotonic one by default, so a wall clock correcting itself
        mid-call never makes a duration wrong.
        """
        self._serializer = serializer
        self._name = name
        self._trace = trace
        self._clock: ClockInterface = clock if clock is not None else MonotonicClock()

    def serialize(
        self,
        data: object,
        format: str,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> str:
        """Return ``data`` written as text in ``format``, recorded."""
        return self._traced(
            _Call("serialize", data, format, context),
            lambda: self._serializer.serialize(data, format, context, type_=type_),
        )

    @overload
    def deserialize[T](
        self,
        data: str | bytes,
        type_: type[T],
        format: str,
        context: Context | None = None,
    ) -> T: ...

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
        """Return the value of type ``type_`` that ``data``, text in ``format``, holds, recorded."""
        return self._traced(
            _Call("deserialize", data, format, context, (type_,)),
            lambda: self._serializer.deserialize(data, type_, format, context),
        )

    def normalize(
        self,
        data: object,
        format: str | None = None,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> NormalizedValue:
        """Return ``data`` as plain data, recorded."""
        return self._traced(
            _Call("normalize", data, format, context),
            lambda: self._serializer.normalize(data, format, context, type_=type_),
        )

    def supports_normalization(
        self,
        data: object,
        format: str | None = None,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
        *,
        type_: object = None,
    ) -> bool:
        """Tell whether the wrapped serializer normalizes ``data``; not recorded."""
        return self._serializer.supports_normalization(data, format, context, type_=type_)

    @overload
    def denormalize[T](
        self,
        data: object,
        type_: type[T],
        format: str | None = None,
        context: Context | None = None,
    ) -> T: ...

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
        """Return a value of type ``type_`` built from ``data``, recorded."""
        return self._traced(
            _Call("denormalize", data, format, context, (type_,)),
            lambda: self._serializer.denormalize(data, type_, format, context),
        )

    def supports_denormalization(
        self,
        data: object,
        type_: object,
        format: str | None = None,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
    ) -> bool:
        """Tell whether the wrapped serializer builds ``type_`` from ``data``; not recorded."""
        return self._serializer.supports_denormalization(data, type_, format, context)

    def get_supported_types(self, format: str | None) -> SupportedTypes:  # noqa: A002 — the name every serializer call uses.
        """Return what the wrapped serializer handles in ``format``; not recorded."""
        return self._serializer.get_supported_types(format)

    def encode(
        self,
        data: NormalizedValue,
        format: str,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
    ) -> str:
        """Return the plain data ``data`` written as text in ``format``, recorded."""
        return self._traced(
            _Call("encode", data, format, context),
            lambda: self._serializer.encode(data, format, context),
        )

    def supports_encoding(self, format: str) -> bool:  # noqa: A002 — the name every serializer call uses.
        """Tell whether the wrapped serializer writes ``format``; not recorded."""
        return self._serializer.supports_encoding(format)

    def decode(
        self,
        data: str | bytes,
        format: str,  # noqa: A002 — the name every serializer call uses.
        context: Context | None = None,
    ) -> NormalizedValue:
        """Return the plain data ``data``, text in ``format``, holds, recorded."""
        return self._traced(
            _Call("decode", data, format, context),
            lambda: self._serializer.decode(data, format, context),
        )

    def supports_decoding(self, format: str) -> bool:  # noqa: A002 — the name every serializer call uses.
        """Tell whether the wrapped serializer reads ``format``; not recorded."""
        return self._serializer.supports_decoding(format)

    def _traced[T](self, described: _Call, call: Callable[[], T]) -> T:
        """Make ``call``, recorded as ``described`` when a profiled request is being recorded."""
        if not self._trace.is_recording():
            return call()
        started = self._clock.now()
        try:
            returned = call()
        except Exception as error:
            self._record(
                described,
                started,
                {"class": qualified_name_of(type(error)), "message": str(error)},
            )
            raise
        self._record(described, started, None)
        return returned

    def _record(self, described: _Call, started: DatePoint, error: dict[str, str] | None) -> None:
        target = described.target
        self._trace.record(
            {
                "serializer": self._name,
                "method": described.method,
                "data_type": qualified_name_of(type(described.data)),
                "target_type": written_name_of(target[0]) if target else None,
                "format": described.format,
                "context": [str(key) for key in described.context or {}],
                "duration_ms": (self._clock.now() - started) / _MILLISECOND,
                "error": error,
            }
        )
