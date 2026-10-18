"""What answers the attributes and the channel a request must satisfy for a firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["AccessMapInterface"]


@runtime_checkable
class AccessMapInterface(Protocol):
    """Answers what a request must satisfy, from a firewall's access rules.

    The access listener asks this after authentication: the first rule whose
    matcher claims the request names the attributes the token must satisfy,
    and a request no rule claims has none. The channel half of the answer —
    which scheme the rule demands the request arrive over — is the channel
    listener's to enforce; no rule carries one yet, so every answer pairs its
    attributes with ``None`` until one does.
    """

    async def get_patterns(
        self, request: ServerRequestInterface
    ) -> tuple[tuple[str, ...], str | None]:
        """Return the first matching rule's attributes, and the channel it demands.

        Args:
            request: The request the rules are matched against, as a message.

        Returns:
            The attributes the first rule whose matcher claims ``request``
            requires — an empty tuple when no rule claims it — and the channel
            that rule demands the request arrive over, or ``None`` when it
            demands none.
        """
        ...
