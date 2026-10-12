"""Turning a scope the protocol handles into one that is stored, and back."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.entity.scope import Scope as ScopeEntity
from xtr_security_oauth2_server.value_object.scope import Scope

from .scope_converter_interface import ScopeConverterInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface

__all__ = ["ScopeConverter"]


@final
class ScopeConverter(ScopeConverterInterface):
    """Converts between the scope entity and the scope that is stored.

    Holds nothing, so one instance serves the whole process.
    """

    @override
    def __repr__(self) -> str:
        """Name the type; there is no state to show."""
        return f"{type(self).__name__}()"

    @override
    def to_domain(self, scope: ScopeEntityInterface) -> Scope:
        """Return ``scope`` as the value that is stored."""
        return Scope(scope.get_identifier())

    @override
    def to_domain_sequence(self, scopes: Sequence[ScopeEntityInterface]) -> Sequence[Scope]:
        """Return ``scopes`` as stored values, in the same order."""
        return tuple(self.to_domain(scope) for scope in scopes)

    @override
    def to_entity(self, scope: Scope) -> ScopeEntityInterface:
        """Return ``scope`` as the entity a grant reads."""
        entity = ScopeEntity()
        entity.set_identifier(str(scope))

        return entity

    @override
    def to_entity_sequence(self, scopes: Sequence[Scope]) -> Sequence[ScopeEntityInterface]:
        """Return ``scopes`` as entities, in the same order."""
        return tuple(self.to_entity(scope) for scope in scopes)
