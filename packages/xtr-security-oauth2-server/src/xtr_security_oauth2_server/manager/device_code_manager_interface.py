"""Where stored device codes are read — by either code — written and swept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
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

    async def clear_expired(self) -> int:
        """Forget every code that has expired, and return how many went."""
        ...
