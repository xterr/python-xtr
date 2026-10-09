"""Build a response."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts.response_interface import ResponseInterface

__all__ = ["ResponseFactoryInterface"]


@runtime_checkable
class ResponseFactoryInterface(Protocol):
    """Makes a response, so that a caller need not name the class that is one."""

    def create_response(
        self,
        code: int = 200,
        reason_phrase: str | None = None,
    ) -> ResponseInterface:
        """Return a new response carrying ``code`` and ``reason_phrase``.

        Args:
            code: The status code; ``200`` unless another is asked for.
            reason_phrase: The phrase to go with ``code`` in the response.
                ``None`` — nothing given — lets the factory fill in the
                phrase recommended for the code; ``""`` asks for a response
                with no phrase at all. Those are two different requests, and
                only this tells them apart.

        Returns:
            The response.
        """
        ...
