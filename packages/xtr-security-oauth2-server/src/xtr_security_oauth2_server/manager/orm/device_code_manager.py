"""Device codes in a database, found by either of their two codes."""

from __future__ import annotations

from typing import final

from sqlalchemy import delete, select
from typing_extensions import override
from xtr_clock import ClockInterface  # noqa: TC002 — read at runtime by the container
from xtr_dependency_injection import (
    ScopeFactoryInterface,  # noqa: TC002 — read at runtime by the container
)

from xtr_security_oauth2_server.manager.device_code_manager_interface import (
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.model.device_code import DeviceCode
from xtr_security_oauth2_server.model.device_code_interface import (
    DeviceCodeInterface,  # noqa: TC001 — read at runtime by the container
)
from xtr_security_oauth2_server.persistence.mapping.mapped_table import mapped_table

from ._changed_rows import changed_rows
from ._unit_session import unit_session

__all__ = ["DeviceCodeManager"]


@final
class DeviceCodeManager(DeviceCodeManagerInterface):
    """Reads and writes the stored device codes, and sweeps the expired ones.

    The one manager with two ways in, because the device flow has two halves
    that never meet: the device polls with the device code, and its owner is
    looked up by the short code they typed into a browser. Both reach the same
    row, which is how an approval given in one half is found by the other —
    and why every write is committed: the two halves are different requests,
    often on different workers.

    One of these serves the whole application, and holds no session: every
    read and every write runs in a unit of work of its own, never the
    request's, so storing a code commits nothing the application has pending.
    """

    def __init__(
        self,
        scope_factory: ScopeFactoryInterface,
        connection: str,
        clock: ClockInterface,
    ) -> None:
        """Read and write the device codes of the connection ``connection``."""
        self._scope_factory = scope_factory
        self._connection = connection
        self._clock = clock

    @override
    async def find(self, identifier: str) -> DeviceCodeInterface | None:
        """Return the code stored as ``identifier``, or ``None``."""
        async with unit_session(self._scope_factory, self._connection) as session:
            return await session.get(DeviceCode, identifier)

    @override
    async def find_by_user_code(self, code: str) -> DeviceCodeInterface | None:
        """Return the code whose short user code is ``code``, or ``None``."""
        async with unit_session(self._scope_factory, self._connection) as session:
            read = await session.execute(
                select(DeviceCode).where(mapped_table(DeviceCode).c["user_code"] == code),
            )
            return read.scalars().one_or_none()

    @override
    async def save(self, device_code: DeviceCodeInterface) -> None:
        """Store ``device_code``, and commit it."""
        async with unit_session(self._scope_factory, self._connection) as session:
            session.add(device_code)
            await session.commit()

    @override
    async def clear_expired(self) -> int:
        """Forget every code that has expired, and return how many went."""
        codes = mapped_table(DeviceCode)
        async with unit_session(self._scope_factory, self._connection) as session:
            swept = await session.execute(
                delete(DeviceCode).where(codes.c["expiry"] < self._clock.now()),
            )
            await session.commit()

        return changed_rows(swept)
