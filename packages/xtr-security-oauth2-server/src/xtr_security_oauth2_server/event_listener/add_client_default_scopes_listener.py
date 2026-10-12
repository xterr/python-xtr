"""A client registered without scopes gets the ones this deployment defaults to."""

from __future__ import annotations

from collections.abc import (
    Sequence,  # noqa: TC003 -- container hydrates this constructor at runtime
)
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from xtr_security_oauth2_server.event.pre_save_client_event import PreSaveClientEvent

__all__ = ["AddClientDefaultScopesListener"]


@final
class AddClientDefaultScopesListener:
    """Fills in a client's scopes when it was registered with none.

    Wherever a client comes from — a command, an administration screen, a
    fixture — it passes a client manager, and a manager announces it first. So
    this one rule, applied there, makes "registered with no scopes" mean "gets
    the deployment's default scopes" everywhere instead of in whichever code
    path remembered.

    A client that already has scopes is left alone: those were chosen, and
    adding to them would widen a registration somebody deliberately narrowed.

    With no default scopes configured, a scope-less client stays scope-less —
    and the unchanged rule that a client with no scopes may ask for any scope
    then applies to it, which is what a deployment that never wanted scopes at
    all is asking for.

    It carries no decorator. The bundle registers it, under the name the
    client managers announce, because a listener the library wires itself
    would run in an application that never asked for it.
    """

    __slots__ = ("_default_scopes",)

    def __init__(self, default_scopes: Sequence[str]) -> None:
        """Default a scope-less client to ``default_scopes``."""
        self._default_scopes = tuple(default_scopes)

    @override
    def __repr__(self) -> str:
        """Name the type and the defaults, which are configuration, not secrets."""
        return f"{type(self).__name__}(default_scopes={self._default_scopes!r})"

    def __call__(self, event: PreSaveClientEvent) -> None:
        """Give the client on ``event`` the default scopes, if it has none."""
        client = event.get_client()
        if client.get_scopes():
            return

        _ = client.set_scopes(*(Scope(scope) for scope in self._default_scopes))
