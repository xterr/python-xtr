"""What reads an incoming webhook into events, and answers its sender."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from xtr_http_message_contracts import ResponseInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_remote_event import RemoteEvent

__all__ = ["RequestParserInterface"]

R = TypeVar("R", bound=ResponseInterface)


@runtime_checkable
class RequestParserInterface(Protocol):
    """Reads an incoming webhook into events, and refuses the ones that are not genuine.

    One parser speaks for one sender: it knows which requests are that sender's,
    how that sender signs them, and what its payload means. Everything a sender
    can get wrong — a signature that does not match, a timestamp outside the
    window, a body that is not readable — is one refusal, so the endpoint in
    front of it has a single thing to answer with.

    The endpoint owns the response: an HTTP message is immutable, so a parser
    cannot build one out of nothing and still be sure it carries what the
    application puts on every response. It is handed one and gives back the one
    it changed.
    """

    async def parse(
        self,
        request: ServerRequestInterface,
        secret: str,
    ) -> RemoteEvent | Sequence[RemoteEvent] | None:
        """Read a request into the events it carries.

        Args:
            request: The request that arrived.
            secret: What the sender's signature is checked against.

        Returns:
            The event the request carried, every event when it carried
            several, or ``None`` when it is one to accept and ignore — a
            sender's keep-alive, an event kind this parser does not speak for.

        Raises:
            RejectWebhookError: When the request is refused, whatever the
                reason: a signature that does not match, a replayed timestamp,
                an unreadable payload.
        """
        ...

    async def create_successful_response(self, request: ServerRequestInterface, response: R) -> R:
        """Fill in the answer to a webhook that was read.

        Args:
            request: The request the endpoint received, for a parser whose
                sender wants something of its own echoed back.
            response: The response the endpoint built, to change and give back.

        Returns:
            The response to send, which is ``response`` with the answer on it.
        """
        ...

    async def create_rejected_response(
        self,
        reason: str,
        request: ServerRequestInterface,
        response: R,
    ) -> R:
        """Fill in the answer to a webhook that was refused.

        Args:
            reason: What to tell the sender. A sender is not debugged by the
                receiver, so this is the refusal itself, never what gave it
                away.
            request: The request the endpoint received.
            response: The response the endpoint built, to change and give back.

        Returns:
            The response to send, which is ``response`` with the refusal on it.
        """
        ...
