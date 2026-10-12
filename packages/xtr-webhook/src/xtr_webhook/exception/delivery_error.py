"""An outgoing webhook was not accepted by the receiver."""

from __future__ import annotations

from .webhook_runtime_error import WebhookRuntimeError

__all__ = ["DeliveryError"]


class DeliveryError(WebhookRuntimeError):
    """A receiver answered an outgoing webhook with a status that is not a success.

    Raised rather than returned, because a delivery runs inside a message handler:
    an error is what makes the bus retry it and, once the attempts are spent, keep
    the message instead of dropping it. A receiver that was merely restarting then
    costs nothing, and one that stays broken leaves a message to look at.

    Attributes:
        status_code: What the receiver answered with, or ``0`` when nothing answered.
        url: Where the webhook was going.
    """

    status_code: int
    url: str

    def __init__(self, status_code: int, url: str) -> None:
        """Record where the webhook was going and what came back.

        Args:
            status_code: What the receiver answered with.
            url: Where the webhook was going.
        """
        self.status_code = status_code
        self.url = url
        super().__init__(self._reason())

    def _reason(self) -> str:
        """Why the delivery failed, as the message.

        A subclass that refuses the delivery before it leaves has no answer to
        report, so it says it differently; its own fields are set before this runs.
        """
        return f'The webhook to "{self.url}" was answered with HTTP {self.status_code}.'
