"""The profiler wiring traces each serializer under its name, into the trace the collector reads."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_http_kernel.data_collector import ProfiledRequest
from xtr_http_message import ServerRequest

from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer
from xtr_serializer.bundle._profiler import _collector, _traceable_factory

if TYPE_CHECKING:
    from xtr_serializer.data_collector import SerializerCall


def _serializer() -> Serializer:
    return Serializer([PydanticNormalizer()], [JsonEncoder()])


def test_the_collector_reads_what_every_traced_serializer_records_under_its_name() -> None:
    collector = _collector()
    default = _traceable_factory(None)(_serializer())
    named = _traceable_factory("api")(_serializer())
    collector.begin_request()

    _ = default.serialize(1, "json")
    _ = named.serialize(2, "json")

    data = collector.collect(ProfiledRequest(ServerRequest("GET", "http://app.test/"), 200, {}, {}))
    calls = cast("list[SerializerCall]", data["calls"])
    assert [call["serializer"] for call in calls] == ["default", "api"]
