"""What a document about a token is built through, so a deployment may replace it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface

__all__ = ["IntrospectionResponseTypeInterface"]


@runtime_checkable
class IntrospectionResponseTypeInterface(Protocol):
    """The answer to a question about a token, filled in and then produced.

    The handler that answers the question decides three things — whether the
    token is live, which kind it is and what it says — and hands each over;
    this decides what the document made of them looks like. Keeping them apart
    is what lets a deployment publish fields of its own without the handler
    knowing any of them.

    It is filled in rather than constructed because the handler sets only what
    it worked out: a token it will say nothing about gets the liveness and
    nothing else.
    """

    def set_active(self, active: bool) -> None:
        """Say whether the token is live."""
        ...

    def set_token_type(self, token_type: str) -> None:
        """Say which kind of token was read, so its fields are named for it."""
        ...

    def set_token_data(self, token_data: Mapping[str, object]) -> None:
        """Say what the token carries, as the kind of token it is records it."""
        ...

    def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        """Answer the document on top of ``response``."""
        ...
