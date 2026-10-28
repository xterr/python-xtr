"""A provider that could not be reached or refused a message."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .notifier_runtime_error import NotifierRuntimeError

if TYPE_CHECKING:
    from xtr_http_client_contracts import HttpResponseInterface

__all__ = ["TransportError"]


class TransportError(NotifierRuntimeError):
    """A provider could not be reached, or answered a message with a refusal.

    It is the one error a round-robin or failover transport takes as a sign that
    a transport is down: anything else is a mistake that another transport would
    make too. It carries the response, so a caller can read what the provider
    said, and the client's debug trace of the transfer, when it kept one. A
    provider that could not be reached gave no response: the client raised
    instead, and that error is the cause of this one.

    Attributes:
        response: What the provider answered with, or ``None`` when it never answered.
        debug: The transfer's ``debug`` info, or ``""`` when the client kept none.
    """

    response: HttpResponseInterface | None
    debug: str

    def __init__(self, message: str, response: HttpResponseInterface | None = None) -> None:
        """Record why the send failed and what the provider answered.

        Args:
            message: Why the send failed, in the provider's words where it gave any.
            response: What the provider answered with; ``None`` when it never answered.
        """
        self.response = response
        debug = None if response is None else response.get_info("debug")
        self.debug = debug if isinstance(debug, str) else ""
        super().__init__(message)
