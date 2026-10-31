"""What a message read off the wire is refused for: the class names its event is tagged with."""

from __future__ import annotations

import json

import pytest
from xtr_messenger import EncodedEnvelope, JsonSerializer, MessageDecodingFailedError, name_of
from xtr_serializer import ClassDiscriminatorMapping, JsonEncoder, PydanticNormalizer, Serializer

from tests.fixtures.events import Notice, StrayNotice
from xtr_remote_event import RemoteEvent
from xtr_remote_event.messenger import ConsumeRemoteEventMessage

_FORGED = "forged-tag-from-the-wire"


def _arriving(event: object) -> EncodedEnvelope:
    """Return a message for the consumer of ``stripe`` holding ``event`` as the wire gave it."""
    return EncodedEnvelope(
        body=json.dumps({"type": "stripe", "event": event}),
        headers={"type": name_of(ConsumeRemoteEventMessage)},
    )


def _decode(encoded: EncodedEnvelope) -> object:
    wire = JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))
    return wire.decode(encoded).message


def _event(tag: object) -> dict[str, object]:
    return {"$type": tag, "name": "stripe", "id": "evt_1", "payload": {}}


def test_an_event_tagged_with_its_name_is_read() -> None:
    decoded = _decode(_arriving(_event("remote_event")))

    assert decoded == ConsumeRemoteEventMessage("stripe", RemoteEvent("stripe", "evt_1", {}))


@pytest.mark.parametrize(
    "event",
    [
        _event(_FORGED),
        _event(None),
        {"name": "stripe", "id": "evt_1", "payload": {}},
        {"$type": "remote_event", "name": "stripe"},
        {"$type": "remote_event", "name": "stripe", "id": "evt_1", "payload": [1, 2]},
        [_FORGED],
        _FORGED,
    ],
    ids=[
        "unknown-name",
        "tag-not-a-name",
        "no-tag",
        "missing-fields",
        "payload-not-an-object",
        "event-not-an-object",
        "event-a-string",
    ],
)
def test_an_event_the_hierarchy_cannot_read_is_refused_as_a_decoding_failure(
    event: object,
) -> None:
    with pytest.raises(MessageDecodingFailedError) as refused:
        _ = _decode(_arriving(event))

    assert _FORGED not in str(refused.value)


def test_a_name_another_hierarchy_registered_is_refused() -> None:
    other = ClassDiscriminatorMapping.for_class(Notice)
    assert other is not None
    assert other.types_mapping["test_stray_notice"] is StrayNotice

    with pytest.raises(MessageDecodingFailedError):
        _ = _decode(_arriving({**_event("test_stray_notice"), "text": "hello"}))


def test_a_body_that_is_not_json_is_refused_as_a_decoding_failure() -> None:
    garbled = EncodedEnvelope(
        body='{"type": "stripe", "event": {' + _FORGED,
        headers={"type": name_of(ConsumeRemoteEventMessage)},
    )

    with pytest.raises(MessageDecodingFailedError) as refused:
        _ = _decode(garbled)

    assert _FORGED not in str(refused.value)


def test_a_long_forged_tag_is_refused_without_being_repeated() -> None:
    tag = _FORGED * 20_000

    with pytest.raises(MessageDecodingFailedError) as refused:
        _ = _decode(_arriving(_event(tag)))

    assert _FORGED not in str(refused.value)
