"""What a device code answers to, beyond being a token."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .token_interface import TokenInterface

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["DeviceCodeEntityInterface"]


@runtime_checkable
class DeviceCodeEntityInterface(TokenInterface, Protocol):
    """A token a device polls on while its owner approves it elsewhere.

    Two codes are issued together: this one, which only the device holds and
    polls with, and a short user code its owner reads off the screen and types
    into the verification URI on a device that has a keyboard. The approval the
    owner gives there is recorded here, and the next poll finds it.

    The polling state lives on the token because the server has to answer a
    device that polls too fast, and that answer depends on when this very code
    was last polled.
    """

    def get_user_code(self) -> str:
        """Return the short code the resource owner types in."""
        ...

    def set_user_code(self, user_code: str) -> None:
        """Set the short code the resource owner types in."""
        ...

    def get_verification_uri(self) -> str:
        """Return where the resource owner goes to type the user code."""
        ...

    def set_verification_uri(self, verification_uri: str) -> None:
        """Set where the resource owner goes to type the user code."""
        ...

    def get_verification_uri_complete(self) -> str:
        """Return the verification URI with the user code already in it."""
        ...

    def get_last_polled_at(self) -> datetime | None:
        """Return when this code was last polled, or ``None`` if never."""
        ...

    def set_last_polled_at(self, last_polled_at: datetime) -> None:
        """Record that this code was polled at ``last_polled_at``."""
        ...

    def get_interval(self) -> int:
        """Return how many seconds the device is asked to wait between polls."""
        ...

    def set_interval(self, interval: int) -> None:
        """Ask the device to wait ``interval`` seconds between polls."""
        ...

    def get_user_approved(self) -> bool:
        """Tell whether the resource owner has approved this code."""
        ...

    def set_user_approved(self, user_approved: bool) -> None:
        """Record the resource owner's decision on this code."""
        ...
