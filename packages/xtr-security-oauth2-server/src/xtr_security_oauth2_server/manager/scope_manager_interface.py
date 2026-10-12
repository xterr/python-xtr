"""Where the scopes this deployment knows are read and written."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_oauth2_server.value_object.scope import Scope

__all__ = ["ScopeManagerInterface"]


@runtime_checkable
class ScopeManagerInterface(Protocol):
    """Answers whether this deployment knows a scope name, and records new ones.

    There is nothing to sweep and nothing to revoke: a scope is a name a
    deployment decided on, not a credential with a life of its own. Finding
    one is how a request naming an unknown scope gets refused.
    """

    async def find(self, identifier: str) -> Scope | None:
        """Return the scope named ``identifier``, or ``None`` when unknown."""
        ...

    async def save(self, scope: Scope) -> None:
        """Make ``scope`` one this deployment knows."""
        ...
