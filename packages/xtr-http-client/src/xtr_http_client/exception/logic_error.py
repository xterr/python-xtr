"""This library was used in a way that cannot work."""

from __future__ import annotations

from xtr_http_client_contracts import HttpClientError

__all__ = ["LogicError"]


class LogicError(HttpClientError, RuntimeError):
    """A client was built in a way that cannot work, whatever it is asked to send.

    Building the private-network guard without xtr-http-foundation installed,
    which holds the networks it refuses, is a mistake in the application's
    setup rather than in a request, so retrying it changes nothing.
    """
