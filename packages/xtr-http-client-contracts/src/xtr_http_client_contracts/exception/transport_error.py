"""The transfer itself failed, so there is no response to look at."""

from __future__ import annotations

from .http_client_error import HttpClientError

__all__ = ["TransportError"]


class TransportError(HttpClientError):
    """Nothing usable came back, or the request could never be made.

    A host that will not resolve, a connection refused or reset, a body that
    stopped half way, a certificate the client would not accept — and the one
    case that never touches the network: an option the client does not
    support. A client reports that by raising rather than by ignoring it, so
    an option that was spelled wrong, or that this client cannot honour,
    cannot pass for one it quietly obeyed.

    It is also what reading a response raises once it has been cancelled.

    Attributes:
        reason: What went wrong, naming the URL it went wrong for.
    """

    reason: str

    def __init__(self, reason: str) -> None:
        """Record what went wrong."""
        self.reason = reason
        super().__init__(reason)
