"""An incoming webhook is refused, and the answer to send back says so."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .webhook_error import WebhookError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["RejectWebhookError"]


class RejectWebhookError(WebhookError):
    """An incoming webhook is refused: it carries the answer the sender is given.

    A sender is not debugged by the receiver, so the refusal is one status code
    and, at most, the headers that status needs — never what gave it away. The
    default, 406, says the request was understood and still not acceptable,
    which is what a wrong signature, a stale timestamp or an unreadable payload
    all amount to from the sender's side.

    Attributes:
        status_code: What to answer with.
        headers: Headers the answer must carry, empty unless the status needs any.
    """

    status_code: int
    headers: Mapping[str, str]

    def __init__(
        self,
        status_code: int = 406,
        message: str = "",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Refuse the webhook, and record what to answer.

        Args:
            status_code: What to answer with.
            message: Why it was refused, for this side's logs. It never reaches the sender.
            headers: Headers the answer must carry.
        """
        self.status_code = status_code
        # Copied so the caller's mapping cannot change the answer after the refusal.
        self.headers = {} if headers is None else dict(headers)
        super().__init__(message)
