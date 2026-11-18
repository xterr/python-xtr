"""A traced serializer answers as the one it wraps, and records each call of a profiled request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import anyio
import anyio.lowlevel
import pytest
from xtr_clock import MockClock
from xtr_http_kernel.data_collector import RequestTrace

from tests.support.shapes import Point
from xtr_serializer import (
    DecoderInterface,
    DenormalizerInterface,
    EncoderInterface,
    JsonEncoder,
    NormalizerInterface,
    NotEncodableValueError,
    PydanticNormalizer,
    Serializer,
    SerializerInterface,
)
from xtr_serializer.data_collector import SerializerCall, TraceableSerializer

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_serializer import Context, NormalizedValue


@final
class _SlowEncoder:
    """Writes anything as ``"slow"``, a quarter of a second later on the clock it is handed."""

    def __init__(self, clock: MockClock) -> None:
        self._clock = clock

    def encode(self, data: NormalizedValue, format: str, context: Context | None = None) -> str:
        del data, format, context
        self._clock.sleep(0.25)
        return "slow"

    def supports_encoding(self, format: str) -> bool:
        return format == "slow"


def _traced(
    clock: MockClock | None = None,
) -> tuple[TraceableSerializer, RequestTrace[SerializerCall], Serializer]:
    the_clock = clock or MockClock()
    trace: RequestTrace[SerializerCall] = RequestTrace("test_traceable_serializer")
    inner = Serializer([PydanticNormalizer()], [JsonEncoder(), _SlowEncoder(the_clock)])
    return TraceableSerializer(inner, "api", trace, clock=the_clock), trace, inner


def test_the_slow_encoder_moves_its_clock_on() -> None:
    clock = MockClock("2026-01-01 00:00:00")

    _ = _SlowEncoder(clock).encode(None, "slow")

    assert clock.now().isoformat() == "2026-01-01T00:00:00.250000+00:00"


def test_it_is_every_interface_the_serializer_is() -> None:
    traced, _, _ = _traced()
    # Checked by the type checkers too: each assignment fails them if a signature drifts.
    as_serializer: SerializerInterface = traced
    as_normalizer: NormalizerInterface = traced
    as_denormalizer: DenormalizerInterface = traced
    as_encoder: EncoderInterface = traced
    as_decoder: DecoderInterface = traced

    assert isinstance(as_serializer, SerializerInterface)
    assert isinstance(as_normalizer, NormalizerInterface)
    assert isinstance(as_denormalizer, DenormalizerInterface)
    assert isinstance(as_encoder, EncoderInterface)
    assert isinstance(as_decoder, DecoderInterface)


def test_outside_a_profiled_request_a_call_is_answered_and_not_recorded() -> None:
    traced, trace, _ = _traced()

    written = traced.serialize(Point(1, 2), "json")

    assert written == '{"x":1,"y":2}'
    assert trace.entries() == ()


def test_serialize_records_the_serializer_the_value_class_the_format_and_the_context_keys() -> None:
    traced, trace, _ = _traced()
    trace.begin()

    _ = traced.serialize(Point(1, 2), "json", {"json_indent": 2, "api_token": "s3cr3t"})

    assert trace.entries() == (
        {
            "serializer": "api",
            "method": "serialize",
            "data_type": "Point",
            "target_type": None,
            "format": "json",
            "context": ["json_indent", "api_token"],
            "duration_ms": 0.0,
            "error": None,
        },
    )


def test_deserialize_records_the_type_asked_for_and_returns_the_value() -> None:
    traced, trace, _ = _traced()
    trace.begin()

    read = traced.deserialize('{"x":1,"y":2}', Point, "json")

    assert read == Point(1, 2)
    assert [
        (call["method"], call["data_type"], call["target_type"]) for call in trace.entries()
    ] == [("deserialize", "str", "Point")]


def test_denormalize_records_a_type_expression_as_written() -> None:
    traced, trace, _ = _traced()
    trace.begin()

    read = traced.denormalize([{"x": 1, "y": 2}], list[Point])

    assert read == [Point(1, 2)]
    assert [(call["method"], call["format"], call["target_type"]) for call in trace.entries()] == [
        ("denormalize", None, "list[Point]")
    ]


def _normalize(traced: TraceableSerializer) -> object:
    return traced.normalize(Point(1, 2))


def _encode(traced: TraceableSerializer) -> object:
    return traced.encode({"x": 1}, "json")


def _decode(traced: TraceableSerializer) -> object:
    return traced.decode(b'{"x":1}', "json")


@pytest.mark.parametrize(
    ("method", "call", "expected"),
    [
        ("normalize", _normalize, {"x": 1, "y": 2}),
        ("encode", _encode, '{"x":1}'),
        ("decode", _decode, {"x": 1}),
    ],
)
def test_each_step_on_its_own_is_recorded_under_its_method(
    method: str, call: Callable[[TraceableSerializer], object], expected: object
) -> None:
    traced, trace, _ = _traced()
    trace.begin()

    returned = call(traced)

    assert returned == expected
    assert [one["method"] for one in trace.entries()] == [method]


def test_a_call_that_raises_is_recorded_and_raised_unchanged() -> None:
    traced, trace, inner = _traced()
    trace.begin()
    with pytest.raises(NotEncodableValueError) as expected:
        _ = inner.decode("nope", "json")

    with pytest.raises(NotEncodableValueError) as raised:
        _ = traced.decode("nope", "json")

    assert str(raised.value) == str(expected.value)
    assert [call["error"] for call in trace.entries()] == [
        {"class": "NotEncodableValueError", "message": str(expected.value)}
    ]


def test_the_duration_is_read_off_the_clock_in_milliseconds() -> None:
    traced, trace, _ = _traced(MockClock("2026-01-01 00:00:00"))
    trace.begin()

    _ = traced.serialize(1, "slow")

    assert [call["duration_ms"] for call in trace.entries()] == [250.0]


def test_a_serialize_is_one_entry_whatever_it_normalizes_on_the_way() -> None:
    traced, trace, _ = _traced()
    trace.begin()

    _ = traced.serialize([Point(1, 2), Point(3, 4)], "json", type_=list[Point])

    assert [call["method"] for call in trace.entries()] == ["serialize"]


def test_the_questions_are_answered_as_the_wrapped_serializer_answers_them_unrecorded() -> None:
    traced, trace, inner = _traced()
    trace.begin()

    answers = (
        traced.supports_normalization(Point(1, 2)),
        traced.supports_denormalization({"x": 1, "y": 2}, Point),
        traced.supports_encoding("json"),
        traced.supports_decoding("xml"),
        traced.get_supported_types("json"),
    )

    assert answers == (
        inner.supports_normalization(Point(1, 2)),
        inner.supports_denormalization({"x": 1, "y": 2}, Point),
        True,
        False,
        inner.get_supported_types("json"),
    )
    assert trace.entries() == ()


@pytest.mark.anyio
async def test_two_requests_at_once_each_see_only_their_own_calls() -> None:
    traced, trace, _ = _traced()
    seen: dict[str, list[str]] = {}

    async def request(name: str, value: object) -> None:
        trace.begin()
        _ = traced.serialize(value, "json")
        await anyio.lowlevel.checkpoint()
        _ = traced.serialize(value, "json")
        seen[name] = [call["data_type"] for call in trace.entries()]

    async with anyio.create_task_group() as group:
        _ = group.start_soon(request, "numbers", 1)
        _ = group.start_soon(request, "words", "one")

    assert seen == {"numbers": ["int", "int"], "words": ["str", "str"]}
