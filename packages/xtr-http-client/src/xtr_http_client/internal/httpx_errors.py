"""What a failure of the backend transfer means in this package's own terms.

A caller holding the client interface has never heard of the backend's own
exceptions, so none of them may reach one. The translation is here, in one
place, because the same failure can surface while the head is being read and
again while the body is: the head is read where the request is made, the body
wherever the caller asks for it.
"""

from __future__ import annotations

import httpx

from xtr_http_client.exception import (
    InvalidArgumentError,
    TransportError,
    TransportTimeoutError,
)

__all__ = ["timed_out", "transport_error"]


def transport_error(error: Exception, url: str) -> TransportError:
    """Return the error to raise for a failed transfer, naming the URL it failed for.

    Three kinds are told apart, because a caller does different things about
    them: running out of time is worth trying again, a URL or a scheme the
    backend cannot make a request from is worth correcting, and everything
    else is the network.

    Args:
        error: What the backend raised.
        url: The URL the transfer was for, kept in the message so a failure
            reported far from the call still says what it was about.

    Returns:
        The error to raise, which the caller is to chain onto ``error``.
    """
    said = str(error) or type(error).__name__
    reason = f'{said} for "{url}".'

    if isinstance(error, httpx.TimeoutException):
        return TransportTimeoutError(reason)
    if isinstance(error, (httpx.UnsupportedProtocol, httpx.InvalidURL)):
        return InvalidArgumentError(reason)

    return TransportError(reason)


def timed_out(url: str) -> TransportTimeoutError:
    """Return the error for a transfer that outlasted ``max_duration``.

    The deadline is this package's own rather than the backend's — the whole
    request and response are measured, which nothing in the backend counts —
    so there is no backend error to translate.

    Args:
        url: The URL the transfer was for.

    Returns:
        The error to raise, which the caller is to chain onto the deadline.
    """
    return TransportTimeoutError(f'Maximum duration reached for "{url}".')
