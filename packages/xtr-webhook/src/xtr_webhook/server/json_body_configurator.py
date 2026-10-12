"""The payload written into the body, as the bytes that get signed."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .request_configurator_interface import RequestConfiguratorInterface
from .signature_format import SignatureFormat

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent

    from .outgoing_request import OutgoingRequest
    from .payload_serializer_interface import PayloadSerializerInterface

__all__ = ["JsonBodyConfigurator"]

_TYPE_KEY = "type"
"""Where the Standard Webhooks format expects to read the event's name."""


@final
class JsonBodyConfigurator(RequestConfiguratorInterface):
    """Writes the payload as the body, and says the body is JSON.

    Under any format but the legacy one the event's name is written into the
    payload first, because that format's signature covers the body and nothing
    else: a name carried there is a name the receiver can act on. A payload that
    already says what it is keeps what it says — the application knows its own
    events better than their source name does.

    The payload is copied before that key is added. The event is a record of
    something that happened, and whoever dispatched it may still be holding the
    dict; sending a webhook must not edit it.
    """

    __slots__ = ("_serializer", "_signature_format")

    def __init__(
        self,
        serializer: PayloadSerializerInterface,
        signature_format: SignatureFormat | str = SignatureFormat.LEGACY,
    ) -> None:
        """Configure what writes the payload, and under which format.

        Args:
            serializer: What turns the payload into the bytes that are sent and
                signed.
            signature_format: What the webhook will be signed with, which decides
                whether the event's name is written into the payload. The string a
                configuration carries is accepted.

        Raises:
            InvalidArgumentError: When ``signature_format`` names no format.
        """
        self._serializer = serializer
        self._signature_format = SignatureFormat.parse(signature_format)

    @override
    def configure(self, event: RemoteEvent, secret: str, request: OutgoingRequest) -> None:
        """Write the serialized payload into ``request`` as its body.

        Args:
            event: The event being sent.
            secret: Unused — the body is signed by the signer, not here.
            request: The request being built.
        """
        del secret

        payload: dict[str, object] = event.payload

        if self._signature_format is not SignatureFormat.LEGACY:
            payload = dict(payload)
            if _TYPE_KEY not in payload:
                payload[_TYPE_KEY] = event.name

        request.body = self._serializer.serialize(payload)
        request.headers["Content-Type"] = "application/json"
