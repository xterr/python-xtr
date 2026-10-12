"""The scopes this deployment knows, held in this process."""

from __future__ import annotations

from collections.abc import (
    Iterable,  # noqa: TC003 -- container hydrates this constructor at runtime
)
from typing import final

from typing_extensions import override

from xtr_security_oauth2_server.manager.scope_manager_interface import ScopeManagerInterface
from xtr_security_oauth2_server.value_object.scope import Scope

__all__ = ["ScopeManager"]


@final
class ScopeManager(ScopeManagerInterface):
    """Holds the known scopes in a mapping, for one process.

    Built with the scopes a deployment made available, because that is where
    they come from — a configured list, not a table somebody edits. A scope
    added afterwards is kept all the same, so a test can widen the set without
    rebuilding the manager.
    """

    def __init__(self, scopes: Iterable[str] = ()) -> None:
        """Know exactly the scopes named in ``scopes``."""
        self._scopes: dict[str, Scope] = {name: Scope(name) for name in scopes}

    @override
    def __repr__(self) -> str:
        """Name the type and the scopes known, which are configuration, not secrets."""
        return f"{type(self).__name__}(scopes={tuple(self._scopes)!r})"

    @override
    async def find(self, identifier: str) -> Scope | None:
        """Return the scope named ``identifier``, or ``None`` when unknown."""
        return self._scopes.get(identifier)

    @override
    async def save(self, scope: Scope) -> None:
        """Make ``scope`` one this deployment knows."""
        self._scopes[str(scope)] = scope
