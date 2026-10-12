"""Who receives an outgoing webhook, and the secret it is signed with."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from xtr_webhook.exception import InvalidArgumentError

__all__ = ["Subscriber"]


@final
@dataclass(frozen=True, slots=True)
class Subscriber:
    """One receiver of outgoing webhooks: where they go, and what signs them.

    The pair travels together because neither is useful alone — a url without a
    secret cannot be signed for, and a secret belongs to exactly one receiver. It
    is frozen so the url cannot be changed after a signature was made over it, and
    so one can be put on a message bus and read back as it was sent.

    Attributes:
        url: Where the webhook is posted.
        secret: What its signature is made with. Kept out of ``repr`` so a log
            line, a traceback or a dumped message cannot carry it.
    """

    url: str
    secret: str = field(repr=False)

    def __post_init__(self) -> None:
        """Refuse a subscriber nothing could be signed for.

        An empty secret still signs — over the empty key — so it would send
        perfectly formed webhooks no receiver can accept. That is a
        misconfiguration to fix, not a request to refuse, so it is caught here
        rather than at the first delivery.
        """
        if not self.secret:
            raise InvalidArgumentError("A non-empty secret is required.")
