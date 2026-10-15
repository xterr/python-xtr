"""What answers which attribute a request must satisfy for a firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["AccessMapInterface"]


@runtime_checkable
class AccessMapInterface(Protocol):
    """Answers the attribute a request must hold, from a firewall's access rules.

    The access listener asks this after authentication: the first rule whose
    matcher claims the request names the one attribute the token must satisfy,
    and a request no rule claims has none.
    """

    async def get_attribute(self, request: ServerRequestInterface) -> str | None:
        """Return the attribute the first matching rule requires, or ``None``."""
        ...
