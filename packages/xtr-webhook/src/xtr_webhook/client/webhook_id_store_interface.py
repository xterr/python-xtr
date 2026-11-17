"""Where the ids of the webhooks already taken are remembered, so a retried one is handled once."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["WebhookIdStoreInterface"]


@runtime_checkable
class WebhookIdStoreInterface(Protocol):
    """Remembers which webhook ids were taken, for as long as a sender may retry them.

    A sender that never received the answer to a webhook sends it again, with
    the same id. The endpoint asks this store before handing an event on: an id
    it already remembers is acknowledged and not handled a second time.
    """

    async def remember(self, webhook_id: str, ttl: int) -> bool:
        """Remember ``webhook_id`` for ``ttl`` seconds, telling whether it is new.

        Atomic: of two callers remembering one id at once, exactly one is told
        ``True`` — otherwise two deliveries of one webhook would both be handled.

        Args:
            webhook_id: The id, prefixed with the webhook type it arrived for.
            ttl: How many seconds to remember it.

        Returns:
            ``True`` for the first caller to remember the id, ``False`` after.
        """
        ...

    async def forget(self, webhook_id: str) -> None:
        """Forget ``webhook_id``, so its retry is handled after a failed hand-on."""
        ...
