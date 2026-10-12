"""What a stored device code answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from xtr_security_oauth2_server.value_object.scope import Scope

    from .client_interface import ClientInterface

__all__ = ["DeviceCodeInterface"]


@runtime_checkable
class DeviceCodeInterface(Protocol):
    """A device code as this server remembers it.

    The one token whose record is written to while it is alive, not only at
    the end of its life: the device polls with it, and each poll records when
    it happened so the next one can be told to slow down, while the approval
    its owner gives in a browser lands on the same record minutes later.

    That is why the resource owner, the approval and the last poll have
    setters here and nothing else does.
    """

    def get_identifier(self) -> str:
        """Return the identifier this code is stored under."""
        ...

    def get_expiry(self) -> datetime:
        """Return the instant this code stops being accepted."""
        ...

    def get_user_identifier(self) -> str | None:
        """Return the resource owner who approved this code, or ``None``."""
        ...

    def set_user_identifier(self, user_identifier: str) -> Self:
        """Record that ``user_identifier`` is acting on this code."""
        ...

    def get_client(self) -> ClientInterface:
        """Return the client the device is acting for."""
        ...

    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes the device asked for."""
        ...

    def get_user_code(self) -> str:
        """Return the short code the resource owner types in."""
        ...

    def get_user_approved(self) -> bool:
        """Tell whether the resource owner has approved this code."""
        ...

    def set_user_approved(self, user_approved: bool) -> Self:
        """Record the resource owner's decision on this code."""
        ...

    def get_verification_uri(self) -> str:
        """Return where the resource owner goes to type the user code."""
        ...

    def get_include_verification_uri_complete(self) -> bool:
        """Tell whether the pre-filled verification URI was asked for."""
        ...

    def get_last_polled_at(self) -> datetime | None:
        """Return when this code was last polled, or ``None`` if never."""
        ...

    def set_last_polled_at(self, last_polled_at: datetime) -> Self:
        """Record that this code was polled at ``last_polled_at``."""
        ...

    def get_interval(self) -> int:
        """Return how many seconds the device is asked to wait between polls."""
        ...

    def is_revoked(self) -> bool:
        """Tell whether this code has been redeemed or withdrawn."""
        ...

    def revoke(self) -> Self:
        """Withdraw this code, and answer it so a caller can chain."""
        ...

    @override
    def __str__(self) -> str:
        """Return the identifier, so a stored code reads as its name."""
        ...
