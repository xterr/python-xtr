"""The headers that say which event this is, and when it was sent."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_clock import Clock

from .request_configurator_interface import RequestConfiguratorInterface
from .signature_format import SignatureFormat

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_remote_event import RemoteEvent

    from .outgoing_request import OutgoingRequest

__all__ = ["HeadersConfigurator"]


@final
class HeadersConfigurator(RequestConfiguratorInterface):
    """Writes the id, the timestamp and — unless the format forbids it — the event.

    The timestamp is what lets a receiver refuse a delivery captured yesterday, so
    it is sent whatever the format; under the Standard Webhooks format it is also
    signed, which is what makes refusing one safe.

    The event name is the exception. That format's signature covers no header at
    all, so a name sent as one is a value the receiver cannot trust; it travels in
    the payload instead, written there by
    :class:`JsonBodyConfigurator <xtr_webhook.server.JsonBodyConfigurator>`.
    """

    __slots__ = (
        "_clock",
        "_event_header_name",
        "_id_header_name",
        "_signature_format",
        "_timestamp_header_name",
    )

    def __init__(
        self,
        event_header_name: str = "Webhook-Event",
        id_header_name: str = "Webhook-Id",
        timestamp_header_name: str = "Webhook-Timestamp",
        clock: ClockInterface | None = None,
        signature_format: SignatureFormat | str = SignatureFormat.LEGACY,
    ) -> None:
        """Configure the names and the format this sends under.

        Args:
            event_header_name: The header the event's name goes in.
            id_header_name: The header the event's id goes in.
            timestamp_header_name: The header the send time goes in. The signer
                reads it back under this same name, so changing one means changing
                both.
            clock: Where the send time comes from. ``None`` reads whichever clock
                is in force when the request is configured, so a test can freeze it
                without the configurator having been built inside the frozen scope.
            signature_format: What the webhook will be signed with, which decides
                whether the event name may be sent as a header. The string a
                configuration carries is accepted.

        Raises:
            InvalidArgumentError: When ``signature_format`` names no format.
        """
        self._event_header_name = event_header_name
        self._id_header_name = id_header_name
        self._timestamp_header_name = timestamp_header_name
        self._clock = clock
        self._signature_format = SignatureFormat.parse(signature_format)

    @override
    def configure(self, event: RemoteEvent, secret: str, request: OutgoingRequest) -> None:
        """Write the identifying headers into ``request``.

        Args:
            event: The event being sent.
            secret: Unused — nothing here is signed.
            request: The request being built.
        """
        del secret

        clock = self._clock or Clock.get()
        request.headers[self._id_header_name] = event.id
        request.headers[self._timestamp_header_name] = str(int(clock.now().timestamp()))

        if self._signature_format is not SignatureFormat.STANDARD:
            request.headers[self._event_header_name] = event.name
