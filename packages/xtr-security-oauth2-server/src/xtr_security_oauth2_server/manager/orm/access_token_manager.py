"""Access tokens in a database, unlinked from their refresh tokens before they go."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from sqlalchemy import delete, select, update
from typing_extensions import override
from xtr_clock import ClockInterface  # noqa: TC002 — read at runtime by the container
from xtr_dependency_injection import (
    ScopeFactoryInterface,  # noqa: TC002 — read at runtime by the container
)

from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.refresh_token import RefreshToken
from xtr_security_oauth2_server.persistence.mapping.mapped_table import mapped_table

from ._unit_session import unit_session

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from xtr_security_oauth2_server.model.access_token_interface import AccessTokenInterface

__all__ = ["AccessTokenManager"]


@final
class AccessTokenManager(AccessTokenManagerInterface):
    """Reads and writes the stored access tokens, and sweeps the expired ones.

    A deployment may choose not to write access tokens down at all: a token is
    then a signed document and nothing more, good until it expires. This
    manager is still the one wired, and answers as that choice asks — nothing
    is stored, nothing is found, and there is nothing to sweep.

    Sweeping unlinks before it deletes. A refresh token outlives the access
    token it was issued beside — that is the point of it — so the rows naming
    a token about to go are cleared first, and only then are the tokens
    deleted. Doing it the other way round leaves the database to decide, and
    not every one of them would answer the same.

    One of these serves the whole application. It holds no session: every
    read and every write runs in a unit of work of its own, never the
    request's, so issuing a token commits nothing the application has pending
    and no rollback of the request takes a token back.
    """

    def __init__(
        self,
        scope_factory: ScopeFactoryInterface,
        connection: str,
        clock: ClockInterface,
        persist_access_token: bool,
    ) -> None:
        """Read and write the access tokens of the connection named ``connection``.

        Args:
            scope_factory: What opens the unit of work each read and write
                runs in.
            connection: Which connection's session the unit reads and writes.
            clock: What decides whether a token has expired.
            persist_access_token: Whether access tokens are written down.
        """
        self._scope_factory = scope_factory
        self._connection = connection
        self._clock = clock
        self._persist_access_token = persist_access_token

    @override
    async def find(self, identifier: str) -> AccessTokenInterface | None:
        """Return the token stored as ``identifier``, or ``None``."""
        if not self._persist_access_token:
            return None

        async with unit_session(self._scope_factory, self._connection) as session:
            return await session.get(AccessToken, identifier)

    @override
    async def save(self, access_token: AccessTokenInterface) -> None:
        """Store ``access_token``, and commit it.

        Committed rather than left to the unit of work, so a token is never
        handed out that another worker cannot read back.
        """
        if not self._persist_access_token:
            return
        async with unit_session(self._scope_factory, self._connection) as session:
            session.add(access_token)
            await session.commit()

    @override
    async def clear_expired(self) -> int:
        """Forget every token that has expired, and return how many went.

        A token expiring at this very instant is kept: it is still being
        accepted, and sweeping it would refuse a request the server would
        otherwise have honoured.
        """
        if not self._persist_access_token:
            return 0
        async with unit_session(self._scope_factory, self._connection) as session:
            expired = await self._expired(session)
            if not expired:
                return 0
            await self._unlink(session, expired)
            _ = await session.execute(
                delete(AccessToken).where(mapped_table(AccessToken).c["identifier"].in_(expired)),
            )
            await session.commit()

        return len(expired)

    async def _expired(self, session: AsyncSession) -> Sequence[str]:
        """Return the identifiers of the tokens that are no longer accepted."""
        tokens = mapped_table(AccessToken)
        read = await session.execute(
            select(tokens.c["identifier"]).where(tokens.c["expiry"] < self._clock.now()),
        )

        return cast("Sequence[str]", tuple(read.scalars().all()))

    async def _unlink(self, session: AsyncSession, expired: Sequence[str]) -> None:
        """Clear the pointer of every refresh token naming one of ``expired``."""
        beside = mapped_table(RefreshToken).c["access_token"]
        _ = await session.execute(
            update(RefreshToken).where(beside.in_(expired)).values({beside: None}),
        )
