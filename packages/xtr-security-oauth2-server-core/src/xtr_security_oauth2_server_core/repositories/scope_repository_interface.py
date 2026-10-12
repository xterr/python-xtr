"""Where scopes are read from, and where the granted set is decided."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .repository_interface import RepositoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.scope_entity_interface import ScopeEntityInterface

__all__ = ["ScopeRepositoryInterface"]


@runtime_checkable
class ScopeRepositoryInterface(RepositoryInterface, Protocol):
    """Turns a scope name into a scope, and decides what is actually granted.

    The two halves are different questions. Looking a scope up answers
    "does this deployment know this name at all", and an unknown name makes
    the request invalid. Finalising answers "and of the known ones, what does
    this client, this grant and this resource owner actually get" — which is
    where a deployment adds the scopes a client always has, drops the ones a
    particular grant may not hand out, or narrows a set to what a user
    consented to.
    """

    async def get_scope_entity_by_identifier(
        self,
        identifier: str,
    ) -> ScopeEntityInterface | None:
        """Return the scope named ``identifier``, or ``None`` when unknown."""
        ...

    async def finalize_scopes(
        self,
        scopes: Sequence[ScopeEntityInterface],
        grant_type: str,
        client_entity: ClientEntityInterface,
        user_identifier: str | None = None,
        auth_code_id: str | None = None,
    ) -> Sequence[ScopeEntityInterface]:
        """Return the scopes actually granted, from the ones requested.

        Scopes may be added, removed or left as they are. The set returned is
        the set written into the token, so this is the last word on what a
        token may do.

        The arguments are the whole of the context a decision can need, and
        they stay separate arguments rather than becoming one object because
        this is the contract an application implements: a deployment reads the
        two or three it cares about and ignores the rest.

        Args:
            scopes: The scopes requested, each already known to this
                repository.
            grant_type: The grant handing them out.
            client_entity: The client asking.
            user_identifier: The resource owner the token will act for, or
                ``None`` when the client acts for itself.
            auth_code_id: The authorization code being redeemed, when one is —
                so a deployment can narrow the set to what was consented to
                when the code was issued.
        """
        ...
