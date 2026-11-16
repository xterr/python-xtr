"""Refresh tokens in a database, withdrawn by exactly one caller."""

from __future__ import annotations

from typing import final

from sqlalchemy import delete, update
from typing_extensions import override
from xtr_clock import ClockInterface  # noqa: TC002 — read at runtime by the container
from xtr_dependency_injection import (
    ScopeFactoryInterface,  # noqa: TC002 — read at runtime by the container
)

from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (
    RefreshTokenManagerInterface,
)
from xtr_security_oauth2_server.model.refresh_token import RefreshToken
from xtr_security_oauth2_server.model.refresh_token_interface import (
    RefreshTokenInterface,  # noqa: TC001 — read at runtime by the container
)
from xtr_security_oauth2_server.persistence.mapping.mapped_table import mapped_table

from ._changed_rows import changed_rows
from ._unit_session import unit_session

__all__ = ["RefreshTokenManager"]

_WITHDRAWN = 1
"""How many rows a revocation changes when it is the one that withdrew the token."""


@final
class RefreshTokenManager(RefreshTokenManagerInterface):
    """Reads and writes the stored refresh tokens, and revokes one atomically.

    :meth:`revoke` is one statement that revokes a token only if it is not
    revoked already, and answers with whether it changed anything. That is
    what closes the window two concurrent refreshes would otherwise race
    through: both can read a token as valid, but only one update finds it
    valid, so only one caller is handed a new access token.

    Where a deployment persists no access token there is no column pointing at
    one, so a refresh token reads back naming none — which is the truth: the
    access token it was issued beside was never written down.

    One of these serves the whole application, and holds no session: every
    read and every write runs in a unit of work of its own, never the
    request's, so storing a token commits nothing the application has pending.
    """

    def __init__(
        self,
        scope_factory: ScopeFactoryInterface,
        connection: str,
        clock: ClockInterface,
    ) -> None:
        """Read and write the refresh tokens of the connection ``connection``."""
        self._scope_factory = scope_factory
        self._connection = connection
        self._clock = clock

    @override
    async def find(self, identifier: str) -> RefreshTokenInterface | None:
        """Return the token stored as ``identifier``, or ``None``."""
        async with unit_session(self._scope_factory, self._connection) as session:
            return await session.get(RefreshToken, identifier)

    @override
    async def save(self, refresh_token: RefreshTokenInterface) -> None:
        """Store ``refresh_token``, and commit it."""
        async with unit_session(self._scope_factory, self._connection) as session:
            session.add(refresh_token)
            await session.commit()

    @override
    async def revoke(self, identifier: str) -> bool:
        """Withdraw the token stored as ``identifier``, in one step.

        Returns:
            Whether this call is what withdrew it: ``True`` when the statement
            found a token that was valid, ``False`` when it was already
            revoked or was never stored.
        """
        tokens = mapped_table(RefreshToken)
        async with unit_session(self._scope_factory, self._connection) as session:
            withdrawn = await session.execute(
                update(RefreshToken)
                .where(tokens.c["identifier"] == identifier, tokens.c["revoked"].is_(False))
                .values({tokens.c["revoked"]: True}),
            )
            await session.commit()

        return changed_rows(withdrawn) == _WITHDRAWN

    @override
    async def clear_expired(self) -> int:
        """Forget every token that has expired, and return how many went."""
        tokens = mapped_table(RefreshToken)
        async with unit_session(self._scope_factory, self._connection) as session:
            swept = await session.execute(
                delete(RefreshToken).where(tokens.c["expiry"] < self._clock.now()),
            )
            await session.commit()

        return changed_rows(swept)
