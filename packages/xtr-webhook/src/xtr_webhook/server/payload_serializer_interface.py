"""How a payload becomes the bytes a webhook is signed over."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["PayloadSerializerInterface"]


@runtime_checkable
class PayloadSerializerInterface(Protocol):
    """Turns a payload into the exact bytes that are sent and signed.

    Its own contract rather than a parameter on the body configurator, because an
    application sending events whose payloads carry dates, decimals or domain
    objects has to decide how those are written, and that decision must be made
    once: the signature covers the bytes this returns, so anything that rewrites
    them afterwards breaks it.
    """

    def serialize(self, payload: Mapping[str, object]) -> bytes:
        """Return the bytes ``payload`` is sent as.

        Args:
            payload: What to write. Never modified — the caller may be holding
                the event's own payload.

        Returns:
            The bytes to send, which are also the bytes signed.
        """
        ...
