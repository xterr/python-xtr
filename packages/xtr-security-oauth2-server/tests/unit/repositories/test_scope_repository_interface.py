"""The scope storage contract looks a scope up and finalises a set of them."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from tests.support.entities import make_scope
from xtr_security_oauth2_server.repositories.scope_repository_interface import (
    ScopeRepositoryInterface,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface


@final
class _ScopeRepository:
    """Knows two scopes, and hands back whatever was asked for unchanged."""

    async def get_scope_entity_by_identifier(
        self,
        identifier: str,
    ) -> ScopeEntityInterface | None:
        if identifier not in {"read", "write"}:
            return None
        return make_scope(identifier)

    async def finalize_scopes(
        self,
        scopes: Sequence[ScopeEntityInterface],
        grant_type: str,
        client_entity: ClientEntityInterface,
        user_identifier: str | None = None,
        auth_code_id: str | None = None,
    ) -> Sequence[ScopeEntityInterface]:
        del grant_type, client_entity, user_identifier, auth_code_id
        return scopes


@final
class _WithoutFinalize:
    """A repository that looks a scope up but never finalises a set."""

    async def get_scope_entity_by_identifier(
        self,
        identifier: str,
    ) -> ScopeEntityInterface | None:
        del identifier
        return None


def test_a_full_repository_satisfies_the_contract() -> None:
    repository: ScopeRepositoryInterface = _ScopeRepository()
    assert isinstance(repository, ScopeRepositoryInterface)


def test_a_repository_missing_a_method_does_not_satisfy_it() -> None:
    assert not isinstance(_WithoutFinalize(), ScopeRepositoryInterface)
