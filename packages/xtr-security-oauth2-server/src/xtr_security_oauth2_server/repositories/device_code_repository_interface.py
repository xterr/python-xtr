"""Where device codes are minted, stored, found again and revoked."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .repository_interface import RepositoryInterface

if TYPE_CHECKING:
    from xtr_security_oauth2_server.entities.device_code_entity_interface import (
        DeviceCodeEntityInterface,
    )

__all__ = ["DeviceCodeRepositoryInterface"]


@runtime_checkable
class DeviceCodeRepositoryInterface(RepositoryInterface, Protocol):
    """Mints the device-code entity, stores it, finds it again, and ends its life.

    This is the one storage contract with a lookup, because the device flow is
    the one flow that has to read a token back: the device polls with the code
    it was given, and every poll reads the stored code to see whether its
    owner has approved it yet and how long ago it was last polled.

    Storing is one method rather than two — there is no separate "store a new
    one" — because a poll writes to the very code it just read.
    """

    async def get_new_device_code(self) -> DeviceCodeEntityInterface:
        """Return a new, unstored device code."""
        ...

    async def persist_device_code(self, device_code_entity: DeviceCodeEntityInterface) -> None:
        """Store ``device_code_entity``, new or already known.

        Raises:
            UniqueTokenIdentifierConstraintViolationError: When a *new* code
                takes an identifier already stored. The grant answers by
                minting another identifier and trying again.
        """
        ...

    async def get_device_code_entity_by_device_code(
        self,
        device_code: str,
    ) -> DeviceCodeEntityInterface | None:
        """Return the stored code named ``device_code``, or ``None``."""
        ...

    async def revoke_device_code(self, code_id: str) -> None:
        """Stop accepting the device code named ``code_id``.

        Revoking one that is unknown, or already revoked, is not an error:
        what the caller asked for is already true.
        """
        ...

    async def is_device_code_revoked(self, code_id: str) -> bool:
        """Tell whether the device code named ``code_id`` was revoked."""
        ...
