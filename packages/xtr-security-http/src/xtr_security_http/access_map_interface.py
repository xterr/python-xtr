"""What answers which attribute a request must satisfy for a firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request

__all__ = ["AccessMapInterface"]


@runtime_checkable
class AccessMapInterface(Protocol):
    """Answers the attribute a request must hold, from a firewall's access rules.

    The access listener asks this after authentication: the first rule whose
    matcher claims the request names the one attribute the token must satisfy,
    and a request no rule claims has none.
    """

    def get_attribute(self, request: Request) -> str | None:
        """Return the attribute the first matching rule requires, or ``None``."""
        ...
