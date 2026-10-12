"""The payload written as JSON, which is what a receiver expects."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import msgspec
from typing_extensions import override

from .payload_serializer_interface import PayloadSerializerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["JsonPayloadSerializer"]


@final
class JsonPayloadSerializer(PayloadSerializerInterface):
    """Writes the payload as compact JSON, keys in the order they were added.

    The default, because a webhook is JSON unless a receiver says otherwise. It
    adds no whitespace and reorders nothing: the bytes are the signed message, so
    two runs over the same payload have to produce the same ones, and a receiver
    that signs what arrived has to arrive at the same digest.
    """

    __slots__ = ()

    @override
    def serialize(self, payload: Mapping[str, object]) -> bytes:
        """Return ``payload`` as JSON.

        Args:
            payload: What to write.

        Returns:
            The compact JSON encoding.

        Raises:
            TypeError: When the payload holds a value JSON has no form for. It is
                not wrapped: the payload came from the application, and what a
                serializer refuses is the serializer's own vocabulary.
        """
        return msgspec.json.encode(payload)
