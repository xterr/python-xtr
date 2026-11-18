"""Device codes kept in this process, found by either of their two codes."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from xtr_clock import (
    ClockInterface,  # noqa: TC002 -- container hydrates this constructor at runtime
)

from xtr_security_oauth2_server.manager.device_code_manager_interface import (
    DeviceCodeManagerInterface,
)

if TYPE_CHECKING:
    from datetime import datetime

    from xtr_security_oauth2_server.model.device_code_interface import DeviceCodeInterface

__all__ = ["DeviceCodeManager"]


@final
class DeviceCodeManager(DeviceCodeManagerInterface):
    """Holds the device codes in a mapping, for one process.

    For tests and single-process demonstrations. The lookup by user code walks
    what is held rather than keeping a second mapping: a demonstration has a
    handful of live codes, and one index that can fall out of step with the
    other is one too many.
    """

    def __init__(self, clock: ClockInterface) -> None:
        """Read expiry against ``clock``."""
        self._clock = clock
        self._device_codes: dict[str, DeviceCodeInterface] = {}

    @override
    def __repr__(self) -> str:
        """Name the type and how many codes are held, never which."""
        return f"{type(self).__name__}(held={len(self._device_codes)})"

    @override
    async def find(self, identifier: str) -> DeviceCodeInterface | None:
        """Return the code stored as ``identifier``, or ``None``."""
        return self._device_codes.get(identifier)

    @override
    async def find_by_user_code(self, code: str) -> DeviceCodeInterface | None:
        """Return the code whose short user code is ``code``, or ``None``."""
        for device_code in self._device_codes.values():
            if device_code.get_user_code() == code:
                return device_code

        return None

    @override
    async def save(self, device_code: DeviceCodeInterface) -> None:
        """Store ``device_code``, new or already known."""
        self._device_codes[device_code.get_identifier()] = device_code

    @override
    async def revoke(self, identifier: str) -> bool:
        """Spend the code stored as ``identifier``, and say whether this call did."""
        code = self._device_codes.get(identifier)
        if code is None or code.is_revoked():
            return False

        _ = code.revoke()

        return True

    @override
    async def record_decision(
        self,
        identifier: str,
        user_identifier: str,
        *,
        user_approved: bool,
    ) -> bool:
        """Record the first decision on a live code, and say whether this call did."""
        code = self._device_codes.get(identifier)
        if (
            code is None
            or code.is_revoked()
            or code.get_user_identifier() is not None
            or code.get_expiry() < self._clock.now()
        ):
            return False

        _ = code.set_user_identifier(user_identifier).set_user_approved(user_approved)

        return True

    @override
    async def record_poll(
        self,
        identifier: str,
        last_polled_at: datetime | None,
        polled_at: datetime,
    ) -> bool:
        """Record a poll unless another was recorded since ``last_polled_at`` was read."""
        code = self._device_codes.get(identifier)
        if code is None or code.get_last_polled_at() != last_polled_at:
            return False

        _ = code.set_last_polled_at(polled_at)

        return True

    @override
    async def clear_expired(self) -> int:
        """Forget every code that has expired, and return how many went."""
        now = self._clock.now()
        kept = {
            identifier: code
            for identifier, code in self._device_codes.items()
            if code.get_expiry() >= now
        }
        cleared = len(self._device_codes) - len(kept)
        self._device_codes = kept

        return cleared
