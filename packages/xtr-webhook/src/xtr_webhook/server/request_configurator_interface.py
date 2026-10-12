"""What one step of building an outgoing webhook looks like."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent

    from .outgoing_request import OutgoingRequest

__all__ = ["RequestConfiguratorInterface"]


@runtime_checkable
class RequestConfiguratorInterface(Protocol):
    """One step of turning an event into the request that carries it.

    Sending a webhook is several decisions — which headers name the event, how the
    payload is written, what signs it — and a receiver dictates them separately.
    Keeping each a configurator of its own means an application that needs a header
    one receiver insists on adds a step rather than replacing the sender.

    The steps run in order and share one request, so a later one can read what an
    earlier one wrote. That is what lets the signer sign the body and the timestamp
    the two before it produced.
    """

    def configure(self, event: RemoteEvent, secret: str, request: OutgoingRequest) -> None:
        """Write this step's part of ``event`` into ``request``.

        Args:
            event: The event being sent.
            secret: The receiving subscriber's secret. Every step is handed it, so
                a step that signs needs nothing else; a step that does not, ignores
                it.
            request: The request being built, written into in place.
        """
        ...
