"""Where stored device codes are read — by either code — written and swept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from xtr_security_oauth2_server.model.device_code_interface import DeviceCodeInterface

__all__ = ["DeviceCodeManagerInterface"]


@runtime_checkable
class DeviceCodeManagerInterface(Protocol):
    """Reads and writes the stored device codes, and sweeps the expired ones.

    The one storage contract with two ways in, because the device flow has two
    halves that never meet: the device polls with the device code, and its
    owner is looked up by the short code they typed into a browser. Both reach
    the same record, which is how an approval given in one half is found by
    the other.
    """

    async def find(self, identifier: str) -> DeviceCodeInterface | None:
        """Return the code stored as ``identifier``, or ``None``."""
        ...

    async def find_by_user_code(self, code: str) -> DeviceCodeInterface | None:
        """Return the code whose short user code is ``code``, or ``None``."""
        ...

    async def save(self, device_code: DeviceCodeInterface) -> None:
        """Store ``device_code``, new or already known."""
        ...

    async def revoke(self, identifier: str) -> bool:
        """Spend the code stored as ``identifier``, in one step.

        Returns:
            Whether this call is what spent it: ``True`` when the code was
            valid and is now revoked, ``False`` when it was already revoked or
            was never stored.
        """
        ...

    async def record_decision(
        self,
        identifier: str,
        user_identifier: str,
        *,
        user_approved: bool,
    ) -> bool:
        """Record what ``user_identifier`` decided about the code, in one step.

        Recorded only while the code is unspent and unexpired and nobody has
        decided yet, so the first decision is the one that holds.

        Returns:
            Whether this call is what recorded it.
        """
        ...

    async def record_poll(
        self,
        identifier: str,
        last_polled_at: datetime | None,
        polled_at: datetime,
    ) -> bool:
        """Record a poll at ``polled_at``, in one step, if no other was since ``last_polled_at``.

        Returns:
            Whether this call is what recorded it.
        """
        ...

    async def clear_expired(self) -> int:
        """Forget every code that has expired, and return how many went."""
        ...
