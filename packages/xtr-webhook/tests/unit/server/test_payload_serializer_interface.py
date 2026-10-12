from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_webhook.server import JsonPayloadSerializer, PayloadSerializerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping


def test_the_json_serializer_satisfies_it() -> None:
    assert isinstance(JsonPayloadSerializer(), PayloadSerializerInterface)


def test_something_that_cannot_serialize_a_payload_does_not() -> None:
    assert not isinstance(object(), PayloadSerializerInterface)


def test_anything_that_turns_a_payload_into_bytes_satisfies_it() -> None:
    class Elsewhere:
        def serialize(self, payload: Mapping[str, object]) -> bytes:
            return repr(dict(payload)).encode()

    assert isinstance(Elsewhere(), PayloadSerializerInterface)
