"""Asks for one event to be signed and delivered to one subscriber."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_messenger import as_message
from xtr_remote_event import RemoteEvent

from xtr_webhook.subscriber import Subscriber

__all__ = ["SendWebhookMessage"]


@as_message(name="xtr_webhook.send.v1")
@final
@dataclass(frozen=True, slots=True)
class SendWebhookMessage:
    """Deliver ``event`` to ``subscriber``.

    What turns deciding to send a webhook into sending one, and the reason the
    two happen in different processes: whatever decided returns at once, and the
    receiver — which may be slow, restarting or gone — is somebody else's wait.

    It carries the subscriber whole rather than an id to look up, because this
    library stores no subscribers; the application knows where a webhook goes
    and what signs it, and says so once, here.

    Attributes:
        subscriber: Where the webhook goes, and the secret it is signed with.
        event: What to deliver, exactly as the sender described it.
    """

    subscriber: Subscriber
    event: RemoteEvent
