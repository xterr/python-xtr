"""The payload written into the body, as the bytes that get signed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from .request_configurator_interface import RequestConfiguratorInterface
from .signature_format import SignatureFormat

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent
    from xtr_serializer import SerializerInterface

    from .outgoing_request import OutgoingRequest

__all__ = ["JsonBodyConfigurator"]

_FORMAT: Final = "json"

_TYPE_KEY: Final = "type"
"""Where the Standard Webhooks format expects to read the event's name."""


@final
class JsonBodyConfigurator(RequestConfiguratorInterface):
    """Writes the event's payload as the body, and says the body is JSON.

    The body is the payload and nothing else, so any receiver reads it as the
    JSON object the sender meant; the event's name and id travel in the
    headers. A field a class derived from
    :class:`~xtr_remote_event.RemoteEvent` adds is not written: what an
    application must say over HTTP goes in the payload.

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
        serializer: SerializerInterface,
        signature_format: SignatureFormat | str = SignatureFormat.LEGACY,
    ) -> None:
        """Configure what writes the payload, and under which format.

        Args:
            serializer: What turns the payload into the JSON that is sent and
                signed — compact, in the payload's own key order, the same
                bytes every time, so a receiver signing what arrived reaches
                the same digest.
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

        Raises:
            NotNormalizableValueError: When the payload holds a value JSON
                cannot carry exactly — a datetime, a set, a tuple. Not wrapped:
                the payload is the application's, and what the serializer
                refuses is said in the serializer's own words, which never
                quote the value.
        """
        del secret

        payload: dict[str, object] = event.payload

        if self._signature_format is not SignatureFormat.LEGACY:
            payload = dict(payload)
            if _TYPE_KEY not in payload:
                payload[_TYPE_KEY] = event.name

        request.body = self._serializer.serialize(payload, _FORMAT).encode()
        request.headers["Content-Type"] = "application/json"
