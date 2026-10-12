"""A serializer that returns scripted bytes and records what it was handed."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_webhook.server import PayloadSerializerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping


@final
class FakePayloadSerializer(PayloadSerializerInterface):
    """Answers ``encoded`` every time; ``payloads`` keeps every call, in order.

    Recording the mapping itself rather than a copy is what lets a test see which
    dict a configurator handed over — the event's own, or a copy of it.
    """

    def __init__(self, encoded: bytes = b'{"fake":true}') -> None:
        self.encoded = encoded
        self.payloads: list[Mapping[str, object]] = []

    @override
    def serialize(self, payload: Mapping[str, object]) -> bytes:
        self.payloads.append(payload)

        return self.encoded
