"""The stored device code: the one record a live flow keeps writing to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override

from ._short_identifier import short_identifier
from .device_code_interface import DeviceCodeInterface

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from xtr_security_oauth2_server.value_object.scope import Scope

    from .client_interface import ClientInterface

__all__ = ["DeviceCode"]


class DeviceCode(DeviceCodeInterface):
    """A device code, its user code, and the state a poll reads and writes."""

    def __init__(  # noqa: PLR0913, PLR0917 -- one stored device code, column for column
        self,
        identifier: str,
        expiry: datetime,
        client: ClientInterface,
        user_identifier: str | None,
        scopes: Sequence[Scope],
        user_code: str,
        user_approved: bool,
        verification_uri: str,
        last_polled_at: datetime | None,
        interval: int,
        *,
        include_verification_uri_complete: bool = False,
    ) -> None:
        """Record a device code and the state of the flow it belongs to.

        ``user_identifier`` and ``user_approved`` are what the browser half of
        the flow puts here, and ``last_polled_at`` is what the device half
        does; all three are ``None``/``False`` on a code that was just issued.
        ``scopes`` is copied, so a caller changing its own list afterwards
        does not change what this code says was asked for.
        """
        self._identifier: str = identifier
        self._expiry: datetime = expiry
        self._client: ClientInterface = client
        self._user_identifier: str | None = user_identifier
        self._scopes: tuple[Scope, ...] = tuple(scopes)
        self._user_code: str = user_code
        self._user_approved: bool = user_approved
        self._verification_uri: str = verification_uri
        self._last_polled_at: datetime | None = last_polled_at
        self._interval: int = interval
        self._include_verification_uri_complete: bool = include_verification_uri_complete
        self._revoked: bool = False

    @override
    def get_identifier(self) -> str:
        """Return the identifier this code is stored under."""
        return self._identifier

    @override
    def get_expiry(self) -> datetime:
        """Return the instant this code stops being accepted."""
        return self._expiry

    @override
    def get_user_identifier(self) -> str | None:
        """Return the resource owner who approved this code, or ``None``."""
        return self._user_identifier

    @override
    def set_user_identifier(self, user_identifier: str) -> Self:
        """Record that ``user_identifier`` is acting on this code."""
        self._user_identifier = user_identifier

        return self

    @override
    def get_client(self) -> ClientInterface:
        """Return the client the device is acting for."""
        return self._client

    @override
    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes the device asked for."""
        return self._scopes

    @override
    def get_user_code(self) -> str:
        """Return the short code the resource owner types in."""
        return self._user_code

    @override
    def get_user_approved(self) -> bool:
        """Tell whether the resource owner has approved this code."""
        return self._user_approved

    @override
    def set_user_approved(self, user_approved: bool) -> Self:
        """Record the resource owner's decision on this code."""
        self._user_approved = user_approved

        return self

    @override
    def get_verification_uri(self) -> str:
        """Return where the resource owner goes to type the user code."""
        return self._verification_uri

    @override
    def get_include_verification_uri_complete(self) -> bool:
        """Tell whether the pre-filled verification URI was asked for.

        Stored rather than worked out again, because the answer belongs to the
        request that started the flow: a device that could not show a QR code
        then will not be able to when it polls either.
        """
        return self._include_verification_uri_complete

    @override
    def get_last_polled_at(self) -> datetime | None:
        """Return when this code was last polled, or ``None`` if never."""
        return self._last_polled_at

    @override
    def set_last_polled_at(self, last_polled_at: datetime) -> Self:
        """Record that this code was polled at ``last_polled_at``."""
        self._last_polled_at = last_polled_at

        return self

    @override
    def get_interval(self) -> int:
        """Return how many seconds the device is asked to wait between polls."""
        return self._interval

    @override
    def is_revoked(self) -> bool:
        """Tell whether this code has been redeemed or withdrawn."""
        return self._revoked

    @override
    def revoke(self) -> Self:
        """Withdraw this code, and answer it so a caller can chain."""
        self._revoked = True

        return self

    @override
    def __str__(self) -> str:
        """Return the identifier, so a stored code reads as its name."""
        return self._identifier

    @override
    def __repr__(self) -> str:
        """Name the type and a cut-short identifier, and nothing else.

        The user code is the credential the resource owner types in, so it is
        left out altogether rather than cut short.
        """
        return f"{type(self).__name__}(identifier={short_identifier(self._identifier)!r})"
