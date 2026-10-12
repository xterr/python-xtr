"""A device code carries the user code, and builds the URI that pre-fills it."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["DeviceCodeTrait"]


class DeviceCodeTrait:
    """Holds the user code, the verification URI and the polling state.

    Compose it with the identifier trait and the token-state trait and a
    device-code entity is complete.

    The polling state is here because answering a device that polls too fast
    depends on when this very code was last polled, and whether a poll
    succeeds depends on an approval given somewhere else entirely — in a
    browser, minutes later.
    """

    _user_approved: bool = False
    _include_verification_uri_complete: bool = False
    _interval: int = 5
    _user_code: str
    _verification_uri: str
    _last_polled_at: datetime | None = None

    def get_user_code(self) -> str:
        """Return the short code the resource owner types in."""
        return self._user_code

    def set_user_code(self, user_code: str) -> None:
        """Set the short code the resource owner types in."""
        self._user_code = user_code

    def get_verification_uri(self) -> str:
        """Return where the resource owner goes to type the user code."""
        return self._verification_uri

    def set_verification_uri(self, verification_uri: str) -> None:
        """Set where the resource owner goes to type the user code."""
        self._verification_uri = verification_uri

    def get_verification_uri_complete(self) -> str:
        """Return the verification URI with the user code already in it.

        This is the URI a device shows as a QR code, so its owner does not
        have to type the code at all. The code is percent-encoded and the
        parameter is joined with ``&`` when the configured URI already carries
        a query, so a verification URI with parameters of its own survives and
        a code holding a character a query reserves still arrives intact.
        """
        separator = "&" if urlsplit(self._verification_uri).query else "?"
        code = quote(self._user_code, safe="")
        return f"{self._verification_uri}{separator}user_code={code}"

    def get_last_polled_at(self) -> datetime | None:
        """Return when this code was last polled, or ``None`` if never."""
        return self._last_polled_at

    def set_last_polled_at(self, last_polled_at: datetime) -> None:
        """Record that this code was polled at ``last_polled_at``."""
        self._last_polled_at = last_polled_at

    def get_interval(self) -> int:
        """Return how many seconds the device is asked to wait between polls."""
        return self._interval

    def set_interval(self, interval: int) -> None:
        """Ask the device to wait ``interval`` seconds between polls."""
        self._interval = interval

    def get_user_approved(self) -> bool:
        """Tell whether the resource owner has approved this code."""
        return self._user_approved

    def set_user_approved(self, user_approved: bool) -> None:
        """Record the resource owner's decision on this code."""
        self._user_approved = user_approved

    def get_verification_uri_complete_in_auth_response(self) -> bool:
        """Tell whether the pre-filled URI goes into the authorization response."""
        return self._include_verification_uri_complete

    def set_verification_uri_complete_in_auth_response(
        self,
        include_verification_uri_complete: bool,
    ) -> None:
        """Choose whether the pre-filled URI goes into the authorization response."""
        self._include_verification_uri_complete = include_verification_uri_complete
