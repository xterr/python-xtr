"""The endpoint every incoming webhook arrives at.

One endpoint for every subscriber: the type in the URL picks the parser that reads
the webhook and the secret it is checked against, so the events it carried reach a
worker and the sender is answered straight away.
"""

from __future__ import annotations

from .webhook_controller import WebhookController

__all__ = ["WebhookController"]
