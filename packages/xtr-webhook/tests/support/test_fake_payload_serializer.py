"""The fake serializer keeps the contract the configurators are written against."""

from __future__ import annotations

from tests.support.fake_payload_serializer import FakePayloadSerializer
from xtr_webhook.server import PayloadSerializerInterface


def test_it_is_a_payload_serializer() -> None:
    assert isinstance(FakePayloadSerializer(), PayloadSerializerInterface)


def test_it_answers_the_bytes_it_was_built_with() -> None:
    serializer = FakePayloadSerializer(b'{"a":1}')

    assert serializer.serialize({"a": 1}) == b'{"a":1}'


def test_it_answers_the_same_bytes_however_often_it_is_called() -> None:
    serializer = FakePayloadSerializer(b"{}")

    assert serializer.serialize({"a": 1}) == serializer.serialize({"b": 2})


def test_it_records_every_payload_in_order() -> None:
    serializer = FakePayloadSerializer()

    _ = serializer.serialize({"first": 1})
    _ = serializer.serialize({"second": 2})

    assert serializer.payloads == [{"first": 1}, {"second": 2}]


def test_it_records_the_mapping_it_was_handed_rather_than_a_copy() -> None:
    serializer = FakePayloadSerializer()
    payload: dict[str, object] = {"a": 1}

    _ = serializer.serialize(payload)

    assert serializer.payloads[0] is payload
