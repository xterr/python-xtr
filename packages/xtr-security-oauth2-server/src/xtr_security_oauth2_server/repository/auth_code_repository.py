"""Minting an authorization code, writing it down, and ending its life."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.converter.scope_converter_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ScopeConverterInterface,
)
from xtr_security_oauth2_server.entity.auth_code import AuthCode
from xtr_security_oauth2_server.exception import (
    UniqueTokenIdentifierConstraintViolationError,
)
from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.client_manager_interface import (
    ClientManagerInterface,
)
from xtr_security_oauth2_server.model.authorization_code import AuthorizationCode
from xtr_security_oauth2_server.repositories.auth_code_repository_interface import (
    AuthCodeRepositoryInterface,
)

from ._stored_client import stored_client_of

if TYPE_CHECKING:
    from xtr_security_oauth2_server.entities.auth_code_entity_interface import (
        AuthCodeEntityInterface,
    )
    from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface

__all__ = ["AuthCodeRepository"]


@final
class AuthCodeRepository(AuthCodeRepositoryInterface):
    """Mints the authorization-code entity, stores it, and revokes it once used.

    The revocation pair here is not an administrator withdrawing anything: it
    is the ordinary end of a code's life. The token endpoint revokes the code
    it just redeemed, and a second attempt with the same code finds it
    revoked — which is the whole of what makes a code single use.
    """

    def __init__(
        self,
        authorization_code_manager: AuthorizationCodeManagerInterface,
        client_manager: ClientManagerInterface,
        scope_converter: ScopeConverterInterface,
    ) -> None:
        """Store codes and read clients through the managers given."""
        self._authorization_code_manager = authorization_code_manager
        self._client_manager = client_manager
        self._scope_converter = scope_converter

    @override
    def __repr__(self) -> str:
        """Name the type; the collaborators say nothing a reader needs."""
        return f"{type(self).__name__}()"

    @override
    async def get_new_auth_code(self) -> AuthCodeEntityInterface:
        """Return a new, unstored authorization code."""
        return AuthCode()

    @override
    async def persist_new_auth_code(self, auth_code_entity: AuthCodeEntityInterface) -> None:
        """Store ``auth_code_entity``.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When a code of that
                identifier is already stored.
            InvalidArgumentError: When no client is stored under the
                identifier the code names.
        """
        identifier = auth_code_entity.get_identifier()
        if await self._authorization_code_manager.find(identifier) is not None:
            raise UniqueTokenIdentifierConstraintViolationError.create()

        client = await stored_client_of(self._client_manager, auth_code_entity.get_client())
        await self._authorization_code_manager.save(
            AuthorizationCode(
                identifier,
                auth_code_entity.get_expiry_date_time(),
                client,
                auth_code_entity.get_user_identifier(),
                self._scope_converter.to_domain_sequence(auth_code_entity.get_scopes()),
            ),
        )

    @override
    async def revoke_auth_code(self, code_id: str) -> None:
        """Stop accepting the authorization code named ``code_id``."""
        code = await self._authorization_code_manager.find(code_id)
        if code is None:
            return

        await self._authorization_code_manager.save(code.revoke())

    @override
    async def is_auth_code_revoked(self, code_id: str) -> bool:
        """Tell whether the authorization code named ``code_id`` was revoked.

        A code nobody stored counts as revoked: every code this server issues
        is written down, so one with no record was never issued here — or has
        already been swept, which is past its ten-minute life anyway.
        """
        code = await self._authorization_code_manager.find(code_id)
        if code is None:
            return True

        return code.is_revoked()
