"""A provider's API that refused an email."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .transport_error import TransportError

if TYPE_CHECKING:
    from xtr_http_client_contracts import HttpResponseInterface

__all__ = ["HttpTransportError"]


class HttpTransportError(TransportError):
    """A provider's API answered an email with a refusal.

    It carries the response, so a caller can read what the provider said beyond
    the message.

    Attributes:
        response: What the provider answered with.
    """

    response: HttpResponseInterface

    def __init__(self, message: str, response: HttpResponseInterface, code: int = 0) -> None:
        """Record why the provider refused the email and what it answered.

        Args:
            message: Why the send failed, in the provider's words where it gave any.
            response: What the provider answered with.
            code: The status the provider answered with, ``0`` when not given.
        """
        self.response = response
        super().__init__(message, code)
