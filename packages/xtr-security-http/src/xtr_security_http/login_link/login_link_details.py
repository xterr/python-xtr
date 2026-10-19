"""One minted login link: where it leads, and until when it counts."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["LoginLinkDetails"]


@final
class LoginLinkDetails:
    """The link a handler minted: its URL and the moment it stops counting.

    The value a handler hands the caller that asked for a link — a mailer
    that sends it, a page that shows it. The URL is the whole link, query
    string and all; the expiry is the moment the hash inside it stops
    verifying, the same moment the caller should stop presenting it.
    """

    __slots__ = ("_expires_at", "_url")

    _url: str
    _expires_at: datetime

    def __init__(self, url: str, expires_at: datetime) -> None:
        """Record the link's URL and the moment it stops counting.

        Args:
            url: The link, whole — the path the handler configured, the
                signed parameters as its query string.
            expires_at: The moment the link's hash stops verifying.
        """
        self._url = url
        self._expires_at = expires_at

    def get_url(self) -> str:
        """Return the link's URL, query string and all."""
        return self._url

    def get_expires_at(self) -> datetime:
        """Return the moment the link stops counting."""
        return self._expires_at

    @override
    def __str__(self) -> str:
        """Return the link's URL: a link is where it leads."""
        return self._url
