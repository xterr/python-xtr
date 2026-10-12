"""An incoming webhook is refused, and the answer to send back says so."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .webhook_error import WebhookError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["RejectWebhookError"]


class RejectWebhookError(WebhookError):
    """An incoming webhook is refused: it carries the answer the sender is given.

    Everything here reaches the sender — the endpoint answers with the status,
    the headers, and the message as a plain-text body. A sender is not debugged
    by the receiver, so the message says which check refused it and nothing
    more: never the values that failed it, nothing an attacker could probe with.
    The default, 406, says the request was understood and still not acceptable,
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
            message: Why it was refused. The endpoint sends it to the sender as
                the answer's plain-text body, so name the check that refused the
                webhook, never the values that failed it.
            headers: Headers the answer must carry.
        """
        self.status_code = status_code
        # Copied so the caller's mapping cannot change the answer after the refusal.
        self.headers = {} if headers is None else dict(headers)
        super().__init__(message)
