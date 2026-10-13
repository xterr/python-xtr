"""A response that has started arriving, and what can be asked of it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from xtr_http_message_contracts import ResponseInterface as MessageResponseInterface

if TYPE_CHECKING:
    from types import TracebackType

__all__ = ["ResponseInterface"]


@runtime_checkable
class ResponseInterface(MessageResponseInterface, Protocol):
    """An HTTP response whose body may still be on its way.

    A response is an HTTP response before it is anything else, so everything
    the message contract describes is here unchanged: the status code and
    reason phrase, the protocol version, the headers, the body as a stream,
    and ``with_*`` copies that leave this one as it was. A copy keeps the
    transfer info and the very same body, so copying a response to add a
    header does not start the transfer again or lose track of it.

    What a client adds is what only a transfer can answer:

    - **It arrives in two steps.** The request is finished once the status
      line and the headers are in; the body follows, and is read when
      somebody asks for it — through ``get_body()`` as a stream,
      :meth:`get_content` in one go, :meth:`to_array` decoded, or
      :meth:`HttpClientInterface.stream
      <xtr_http_client_contracts.http_client_interface.HttpClientInterface.stream>`
      chunk by chunk.
    - **A status is an answer, not a failure.** Nothing raises because a
      server said 404 or 503. Being told is something the caller asks for, by
      reading the content with ``throw`` left on, or by letting an
      ``async with`` block end.
    - **Looking at the status counts.** Any call to ``get_status_code()``,
      ``get_headers()``, :meth:`get_content` or :meth:`to_array` is looking.
      Leaving an ``async with`` block normally over a 3xx, 4xx or 5xx nobody
      looked at raises the matching :class:`HttpError
      <xtr_http_client_contracts.exception.http_error.HttpError>`, so a
      request whose answer was never examined cannot pass for one that went
      well. Reading the headers never raises on its own, whatever the status.
    - **The body is kept by default.** With ``buffer`` left on, reading the
      content twice gives the same bytes. With it off, the second read raises
      :class:`TransportError
      <xtr_http_client_contracts.exception.transport_error.TransportError>`,
      saying ``Cannot get the content of the response twice: buffering is disabled.``
    - **It holds a connection until it is done with.** ``async with`` closes
      the body however the block ends, which is what frees the connection;
      :meth:`cancel` is the same thing said outright, mid-transfer.
    """

    def get_info(self, key: str | None = None) -> object:
        """Return what the transfer knows about itself, as it stands.

        Never raises and never waits, so it can be read while the transfer is
        going on, from a progress callback included. What it reports is live:
        it changes from one call to the next as the transfer progresses.

        These entries are always there:

        - ``canceled`` (``bool``) — whether :meth:`cancel` was called.
        - ``error`` (``str | None``) — what went wrong, once something has.
        - ``http_code`` (``int``) — the last status code, or ``0`` before one
          arrived.
        - ``http_method`` (``str``) — the method of the last request made.
        - ``redirect_count`` (``int``) — how many redirects were followed.
        - ``redirect_url`` (``str | None``) — where a 3xx points, resolved,
          whether or not it was followed.
        - ``response_headers`` — the headers of the last response.
        - ``start_time`` (``float``) — when the request was sent, or ``0.0``
          while it is pending.
        - ``url`` (``str``) — the URL the last request went to, which is the
          last hop of a chain of redirects.
        - ``user_data`` — the ``user_data`` option, or ``None``.

        A client adds what it knows: ``primary_ip`` once connected — which is
        what a caller checks an address against — and ``retry_count`` where
        something retries.

        Args:
            key: One entry to look up. ``None`` asks for all of them.

        Returns:
            A mapping of every entry when ``key`` is ``None``; otherwise the
            value under ``key``, or ``None`` when the client has no such
            entry.
        """
        ...

    async def cancel(self) -> None:
        """Abandon the transfer and let go of what it was holding.

        No further chunk arrives for this response afterwards, and
        ``get_info("canceled")`` reads ``True``. Cancelling a response that
        has already finished does nothing.
        """
        ...

    async def get_content(self, throw: bool = True) -> bytes:
        """Read the whole body, waiting for the rest of it to arrive.

        Args:
            throw: Whether an unsuccessful status is to be raised rather than
                returned. Left on, this is where a 3xx, 4xx or 5xx becomes an
                exception; turned off, the body of the error document comes
                back instead.

        Returns:
            Every byte of the body. The body is empty when there was none.

        Raises:
            TransportError: When the transfer failed, or when the body was
                already read and the response was asked not to keep it.
            RedirectionError: On a 3xx that was not followed, when ``throw``.
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
            DecodingError: When the body is empty, is not JSON, or is JSON
                that is not an object.
            TransportError: When the transfer failed, or when the body was
                already read and the response was asked not to keep it.
            RedirectionError: On a 3xx that was not followed, when ``throw``.
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
        """Close the body, and report a status nobody looked at.

        The body is closed however the block ends, so the connection is freed
        even when the block raises.

        Args:
            exc_type: The class of the exception the block is leaving with,
                or ``None`` when it is leaving normally.
            exc: That exception.
            traceback: Its traceback.

        Raises:
            RedirectionError: When the block ends normally on a 3xx that was
                not followed and nobody looked at the status.
            ClientError: When the block ends normally on a 4xx and nobody
                looked at the status.
            ServerError: When the block ends normally on a 5xx and nobody
                looked at the status.
        """
        ...
