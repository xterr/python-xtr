"""The collector reads the request's serializer calls off the trace, with the counts."""

from __future__ import annotations

from typing import cast

from xtr_http_kernel.data_collector import ProfiledRequest, RequestTrace
from xtr_http_message import ServerRequest

from xtr_serializer.data_collector import SerializerCall, SerializerDataCollector


def _call(method: str, duration_ms: float, error: dict[str, str] | None = None) -> SerializerCall:
    return {
        "serializer": "default",
        "method": method,
        "data_type": "Point",
        "target_type": None,
        "format": "json",
        "context": ["json_indent"],
        "duration_ms": duration_ms,
        "error": error,
    }


def _profiled() -> ProfiledRequest:
    return ProfiledRequest(ServerRequest("GET", "http://app.test/"), 200, {}, {})


def _collector() -> tuple[SerializerDataCollector, RequestTrace[SerializerCall]]:
    trace: RequestTrace[SerializerCall] = RequestTrace("test_serializer_data_collector")
    return SerializerDataCollector(trace), trace


def test_it_is_named_serializer() -> None:
    collector, _ = _collector()

    assert collector.name == "serializer"


def test_with_no_call_it_collects_empty_counts() -> None:
    collector, _ = _collector()
    collector.begin_request()

    data = collector.collect(_profiled())

    assert data == {"calls": [], "count": 0, "duration_ms": 0, "errors": 0, "by_method": {}}


def test_it_collects_every_call_with_the_counts() -> None:
    collector, trace = _collector()
    collector.begin_request()
    failure = {"class": "NotEncodableValueError", "message": "not valid JSON"}
    trace.record(_call("serialize", 1.5))
    trace.record(_call("deserialize", 2.0, failure))
    trace.record(_call("serialize", 0.5))

    data = collector.collect(_profiled())

    assert data == {
        "calls": [
            _call("serialize", 1.5),
            _call("deserialize", 2.0, failure),
            _call("serialize", 0.5),
        ],
        "count": 3,
        "duration_ms": 4.0,
        "errors": 1,
        "by_method": {"serialize": 2, "deserialize": 1},
    }


def test_late_collection_takes_in_the_calls_made_after_the_first() -> None:
    collector, trace = _collector()
    collector.begin_request()
    trace.record(_call("serialize", 1.0))
    early = collector.collect(_profiled())
    trace.record(_call("encode", 1.0))

    data = collector.late_collect(early, _profiled())

    calls = cast("list[SerializerCall]", data["calls"])
    assert [call["method"] for call in calls] == ["serialize", "encode"]
    assert data["count"] == 2


def test_beginning_a_request_forgets_the_calls_of_the_one_before() -> None:
    collector, trace = _collector()
    collector.begin_request()
    trace.record(_call("serialize", 1.0))

    collector.begin_request()

    assert collector.collect(_profiled())["count"] == 0
