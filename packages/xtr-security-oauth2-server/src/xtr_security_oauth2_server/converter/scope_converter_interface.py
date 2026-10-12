"""What turns a scope from one side of the seam into the other."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface
    from xtr_security_oauth2_server.value_object.scope import Scope

__all__ = ["ScopeConverterInterface"]


@runtime_checkable
class ScopeConverterInterface(Protocol):
    """Turns a scope the protocol handles into one that is stored, and back.

    A scope exists twice here: as the entity a grant adds to a token, and as
    the value a client's registration lists and a row holds. Both are a name
    and nothing else, which is why one line converts either way — and why the
    conversion is a service rather than a method on either side: an
    application that brings its own scope entity replaces this and nothing
    else.

    The sequence methods are not sugar. The repositories convert whole sets at
    a time, and doing it in one call keeps the order — the order a token
    reports its scopes in, and the order the ``scope`` claim reads out.
    """

    def to_domain(self, scope: ScopeEntityInterface) -> Scope:
        """Return ``scope`` as the value that is stored."""
        ...

    def to_domain_sequence(self, scopes: Sequence[ScopeEntityInterface]) -> Sequence[Scope]:
        """Return ``scopes`` as stored values, in the same order."""
        ...

    def to_entity(self, scope: Scope) -> ScopeEntityInterface:
        """Return ``scope`` as the entity a grant reads."""
        ...

    def to_entity_sequence(self, scopes: Sequence[Scope]) -> Sequence[ScopeEntityInterface]:
        """Return ``scopes`` as entities, in the same order."""
        ...
