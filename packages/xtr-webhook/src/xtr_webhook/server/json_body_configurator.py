"""The event written into the body, as the bytes that get signed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_remote_event import RemoteEvent

from .request_configurator_interface import RequestConfiguratorInterface

if TYPE_CHECKING:
    from xtr_serializer import SerializerInterface

    from .outgoing_request import OutgoingRequest

__all__ = ["JsonBodyConfigurator"]

_FORMAT: Final = "json"


@final
class JsonBodyConfigurator(RequestConfiguratorInterface):
    """Writes the whole event as the body, and says the body is JSON.

    The event is written as a :class:`~xtr_remote_event.RemoteEvent`, the base
    of its hierarchy: under ``"$type"`` the name its class registered, then its
    fields — ``name``, ``id``, ``payload`` and whatever a derived class adds. So
    a receiver reading it with this library's parser gets back the event that
    was sent, of the same class, and under every format the body itself names
    the event, inside what the signature covers.

    The bytes are the serializer's, compact and in the same order every time:
    the signer runs after this over exactly these bytes, and a receiver signs
    what arrived, so nothing may rewrite them in between.
    """

    __slots__ = ("_serializer",)

    def __init__(self, serializer: SerializerInterface) -> None:
        """Write the event with ``serializer``.

        Args:
            serializer: What turns the event into the JSON that is sent and
                signed — the application's, so the events it declares are
                written exactly as they are read back.
        """
        self._serializer = serializer

    @override
    def configure(self, event: RemoteEvent, secret: str, request: OutgoingRequest) -> None:
        """Write the serialized event into ``request`` as its body.

        Args:
            event: The event being sent.
            secret: Unused — the body is signed by the signer, not here.
            request: The request being built.

        Raises:
            NotNormalizableValueError: When the event holds a value that would
                not read back exactly — a class of the hierarchy that registered
                no name, above all. Not wrapped: the event is the
                application's, and what the serializer refuses is said in the
                serializer's own words.
        """
        del secret

        request.body = self._serializer.serialize(event, _FORMAT, type_=RemoteEvent).encode()
        request.headers["Content-Type"] = "application/json"
