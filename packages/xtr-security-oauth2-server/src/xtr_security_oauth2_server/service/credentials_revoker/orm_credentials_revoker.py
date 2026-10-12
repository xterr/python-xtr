"""Withdrawing everything a user or a client holds, one statement per table."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import select, update
from typing_extensions import override
from xtr_orm import ConnectionRegistry  # noqa: TC002 — read at runtime by the container
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from xtr_security_oauth2_server.manager.client_manager_interface import (
    ClientManagerInterface,  # noqa: TC001 — read at runtime by the container
)
from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.authorization_code import AuthorizationCode
from xtr_security_oauth2_server.model.device_code import DeviceCode
from xtr_security_oauth2_server.model.refresh_token import RefreshToken
from xtr_security_oauth2_server.persistence.mapping.mapped_table import mapped_table
from xtr_security_oauth2_server.service.credentials_revoker_interface import (
    CredentialsRevokerInterface,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_oauth2_server.model.client_interface import ClientInterface

__all__ = ["OrmCredentialsRevoker"]

_FOR_USER = "user_identifier"
"""The column naming the resource owner a credential was issued on behalf of."""

_FOR_CLIENT = "client"
"""The column naming the client a credential was issued to."""


@final
class OrmCredentialsRevoker(CredentialsRevokerInterface):
    """Withdraws every stored credential of a user, or of a client.

    A password change, an account closure or a client being withdrawn all have
    to take back what was already handed out, and none of them arrives as an
    OAuth request. Done as one statement per table rather than by reading the
    credentials and saving them back: an account that has been in use for
    years may hold thousands, and the point of the operation is that none of
    them is left behind.

    Both halves differ only in which column names the holder, so both run the
    same statements. The refresh tokens are reached through the access tokens
    they were issued beside, since that is the only thing a refresh token
    records about who holds it.

    What a deployment does not store it cannot withdraw: with no access-token
    table, an access token stays good until it expires however thoroughly its
    refresh token was revoked, and the refresh tokens have nothing to be
    reached through. The codes are still withdrawn.

    One of these serves the whole application, and holds no session: each
    withdrawal asks the connection registry for the session of the unit of
    work it is being made in.
    """

    def __init__(
        self,
        connections: ConnectionRegistry,
        connection: str,
        client_manager: ClientManagerInterface,
        persist_access_token: bool = True,
        enable_device_code_grant: bool = True,
    ) -> None:
        """Withdraw credentials on ``connection``, of clients ``client_manager`` knows.

        Args:
            connections: Where the session of the unit of work under way is
                asked for.
            connection: Which connection's session that is.
            client_manager: Where a client is read back from, so a withdrawal
                is made against the registration that is stored.
            persist_access_token: Whether access tokens are written down.
            enable_device_code_grant: Whether the device flow is on.
        """
        self._connections = connections
        self._connection = connection
        self._clients = client_manager
        self._persist_access_token = persist_access_token
        self._enable_device_code_grant = enable_device_code_grant

    async def _session(self) -> AsyncSession:
        """Return the session of the unit of work this withdrawal is made in."""
        return await self._connections.session(self._connection)

    @override
    async def revoke_credentials_for_user(self, user: UserInterface) -> None:
        """Withdraw every credential issued on behalf of ``user``."""
        await self._withdraw(_FOR_USER, user.get_user_identifier())

    @override
    async def revoke_credentials_for_client(self, client: ClientInterface) -> None:
        """Withdraw every credential issued to ``client``.

        The registration is read back first, so a withdrawal is made against
        the client that is stored rather than against whatever the caller
        happens to hold.

        Raises:
            InvalidArgumentError: When no client is registered under that
                identifier, which leaves nothing to withdraw and means the
                caller is working from a registration that is gone.
        """
        registered = await self._clients.find(client.get_identifier())
        if registered is None:
            raise InvalidArgumentError(
                f"No client is registered as {client.get_identifier()!r}, so there are no "
                "credentials of its to withdraw.",
            )
        await self._withdraw(_FOR_CLIENT, registered.get_identifier())

    async def _withdraw(self, column: str, holder: str) -> None:
        """Withdraw every credential whose ``column`` names ``holder``."""
        session = await self._session()
        if self._persist_access_token:
            await self._withdraw_tokens(session, column, holder)
        codes = mapped_table(AuthorizationCode)
        _ = await session.execute(
            update(AuthorizationCode)
            .where(codes.c[column] == holder)
            .values({codes.c["revoked"]: True}),
        )
        if self._enable_device_code_grant:
            device = mapped_table(DeviceCode)
            _ = await session.execute(
                update(DeviceCode)
                .where(device.c[column] == holder)
                .values({device.c["revoked"]: True}),
            )
        await session.commit()

    async def _withdraw_tokens(self, session: AsyncSession, column: str, holder: str) -> None:
        """Withdraw the access tokens of ``holder``, and the refresh tokens beside them."""
        tokens = mapped_table(AccessToken)
        held = tokens.c[column] == holder
        _ = await session.execute(
            update(AccessToken).where(held).values({tokens.c["revoked"]: True}),
        )
        refresh = mapped_table(RefreshToken)
        _ = await session.execute(
            update(RefreshToken)
            .where(refresh.c["access_token"].in_(select(tokens.c["identifier"]).where(held)))
            .values({refresh.c["revoked"]: True}),
        )
