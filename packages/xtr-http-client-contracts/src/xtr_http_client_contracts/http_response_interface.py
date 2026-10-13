"""A response that has started arriving, and what a client adds to it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from xtr_http_message_contracts import ResponseInterface

if TYPE_CHECKING:
    from types import TracebackType

__all__ = ["HttpResponseInterface"]


@runtime_checkable
class HttpResponseInterface(ResponseInterface, Protocol):
    """An HTTP response whose body is read off the network when it is asked for.

    It is a message response first: the status code and reason phrase, the
    protocol version, the headers, the body as a stream and the ``with_*``
    copies are the message contract's, so code typed against the plain
    response interface takes this one as it is. A copy keeps the transfer
    info and the very same body.

    What a client adds:

    - **A status is an answer, not a failure.** The response is handed back
      once the status line and the headers are in, whatever the status.
      :meth:`get_content` and :meth:`to_array` raise for a 3xx, 4xx or 5xx
      when ``throw`` is left on, and return the body when it is turned off.
    - **The body is kept.** It is read off the network on demand and kept —
      in a temporary file past 2 MiB — so it can be read again;
      ``get_body()`` is an async stream over that kept body.
    - **It holds a connection until it is done with.** Leaving an
      ``async with`` block closes the body, which frees the connection;
      :meth:`cancel` does the same mid-transfer.
    """

    def get_info(self, key: str | None = None) -> object:
        """Return what the transfer knows about itself, as it stands.

        Never raises and never waits, so it can be read while the transfer is
        going on.

        These entries are always there:

        - ``canceled`` (``bool``) — whether :meth:`cancel` was called.
        - ``error`` (``str | None``) — what went wrong, once something has.
        - ``http_code`` (``int``) — the last status code, or ``0`` before one
          arrived.
        - ``http_method`` (``str``) — the method of the last request made.
        - ``redirect_count`` (``int``) — how many redirects were followed.
        - ``redirect_url`` (``str | None``) — where a 3xx points, resolved,
          when it was not followed.
        - ``response_headers`` (``list[str]``) — the raw status and header
          lines of every hop.
        - ``start_time`` (``float``) — when the request was sent.
        - ``total_time`` (``float``) — how long the transfer has taken.
        - ``url`` (``str``) — the URL of the last hop.
        - ``user_data`` — the ``user_data`` option, or ``None``.

        ``primary_ip`` and ``retry_count`` are there when they are known.

        Args:
            key: One entry to look up. ``None`` asks for all of them.

        Returns:
            A mapping of every entry when ``key`` is ``None``; otherwise the
            value under ``key``, or ``None`` when there is no such entry.
        """
        ...

    async def cancel(self) -> None:
        """Abandon the transfer and let go of what it was holding.

        Afterwards ``get_info("canceled")`` reads ``True`` and
        ``get_info("error")`` reads ``Response has been canceled.``, and
        reading the body raises :class:`TransportError
        <xtr_http_client_contracts.exception.transport_error.TransportError>`
        with that message.
        """
        ...

    async def get_content(self, throw: bool = True) -> bytes:
        """Read the whole body, waiting for the rest of it to arrive.

        Args:
            throw: Whether an unsuccessful status is to be raised rather than
                returned. The message is ``HTTP <code> returned for "<url>".``,
                or the title and detail of the body when it is a JSON problem
                document (RFC 7807, or its hydra form).

        Returns:
            Every byte of the body, empty when there was none.

        Raises:
            TransportError: When the transfer failed or was cancelled.
            RedirectionError: On a 3xx once ``max_redirects`` was reached,
                when ``throw``.
            ClientError: On a 4xx, when ``throw``.
            ServerError: On a 5xx, when ``throw``.
        """
        ...

    async def to_array(self, throw: bool = True) -> dict[str, object]:
        """Read the whole body and decode it as a JSON object.

        Args:
            throw: Whether an unsuccessful status is to be raised rather than
                returned, as in :meth:`get_content`.

        Returns:
            What the body decoded to.

        Raises:
            DecodingError: When the body is empty or is not JSON.
            JsonError: When the body is JSON but not an object.
            TransportError: When the transfer failed or was cancelled.
            RedirectionError: On a 3xx once ``max_redirects`` was reached,
                when ``throw``.
            ClientError: On a 4xx, when ``throw``.
            ServerError: On a 5xx, when ``throw``.
        """
        ...

    async def __aenter__(self) -> Self:
        """Enter a block that owns the transfer.

        Returns:
            This response.
        """
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the body however the block ends, and nothing else.

        Args:
            exc_type: The class of the exception the block is leaving with,
                or ``None`` when it is leaving normally.
            exc: That exception.
            traceback: Its traceback.
        """
        ...
