"""Authorization codes in a database, swept once they expire."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import delete, update
from typing_extensions import override
from xtr_clock import ClockInterface  # noqa: TC002 — read at runtime by the container
from xtr_orm import ConnectionRegistry  # noqa: TC002 — read at runtime by the container

from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.model.authorization_code import AuthorizationCode
from xtr_security_oauth2_server.model.authorization_code_interface import (
    AuthorizationCodeInterface,  # noqa: TC001 — read at runtime by the container
)
from xtr_security_oauth2_server.persistence.mapping.mapped_table import mapped_table

from ._changed_rows import changed_rows

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["AuthorizationCodeManager"]

_SPENT = 1
"""How many rows a revocation changes when it is the one that spent the code."""


@final
class AuthorizationCodeManager(AuthorizationCodeManagerInterface):
    """Reads and writes the stored authorization codes, and sweeps the expired ones.

    A code lives for minutes and is redeemed once, so what is stored is only
    enough to refuse the second attempt — and the second attempt has to be
    refused across every worker, which is why the revoked flag is read from
    the database rather than remembered.

    Sweeping matters more here than anywhere else: a busy server writes one of
    these per authorization and never reads most of them again.

    One of these serves the whole application, and holds no session: every
    read and every write asks the connection registry for the session of the
    request being served.
    """

    def __init__(
        self,
        connections: ConnectionRegistry,
        connection: str,
        clock: ClockInterface,
    ) -> None:
        """Read and write the authorization codes of the connection ``connection``."""
        self._connections = connections
        self._connection = connection
        self._clock = clock

    async def _session(self) -> AsyncSession:
        """Return the session of the unit of work this request is served in."""
        return await self._connections.session(self._connection)

    @override
    async def find(self, identifier: str) -> AuthorizationCodeInterface | None:
        """Return the code stored as ``identifier``, or ``None``."""
        return await (await self._session()).get(AuthorizationCode, identifier)

    @override
    async def save(self, auth_code: AuthorizationCodeInterface) -> None:
        """Store ``auth_code``, and commit it."""
        session = await self._session()
        session.add(auth_code)
        await session.commit()

    @override
    async def revoke(self, identifier: str) -> bool:
        """Spend the code stored as ``identifier``, in one step.

        One conditional statement, so of two redemptions at once only one finds
        the code valid — on every worker, whatever their sessions read before.

        Returns:
            Whether this call is what spent it: ``True`` when the statement
            found a code that was valid, ``False`` when it was already revoked
            or was never stored.
        """
        codes = mapped_table(AuthorizationCode)
        session = await self._session()
        spent = await session.execute(
            update(AuthorizationCode)
            .where(codes.c["identifier"] == identifier, codes.c["revoked"].is_(False))
            .values({codes.c["revoked"]: True})
            .execution_options(synchronize_session="fetch"),
        )
        await session.commit()

        return changed_rows(spent) == _SPENT

    @override
    async def clear_expired(self) -> int:
        """Forget every code that has expired, and return how many went."""
        codes = mapped_table(AuthorizationCode)
        session = await self._session()
        swept = await session.execute(
            delete(AuthorizationCode).where(codes.c["expiry"] < self._clock.now()),
        )
        await session.commit()

        return changed_rows(swept)
