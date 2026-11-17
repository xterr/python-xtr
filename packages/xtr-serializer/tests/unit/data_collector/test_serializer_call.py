"""A recorded call carries exactly the keys a serializer call is declared with."""

from __future__ import annotations

import json

from xtr_http_kernel.data_collector import RequestTrace

from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer
from xtr_serializer.data_collector import SerializerCall, TraceableSerializer


def _recorded() -> SerializerCall:
    trace: RequestTrace[SerializerCall] = RequestTrace("test_serializer_call")
    traced = TraceableSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]), "x", trace)
    trace.begin()
    _ = traced.serialize(1, "json")
    return trace.entries()[0]


def test_a_recorded_call_has_every_declared_key_and_no_other() -> None:
    assert set(_recorded()) == set(SerializerCall.__annotations__)


def test_a_recorded_call_is_plain_json_data() -> None:
    recorded = _recorded()

    assert json.loads(json.dumps(recorded)) == recorded
