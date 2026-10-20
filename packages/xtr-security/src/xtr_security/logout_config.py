"""The logout a firewall's requests can ask for, described as inert data.

A firewall with one carries a logout step in its chain — the request that asks
for the logout path is logged out — and the logout event it announces is
answered by the listeners this configuration turns on, each doing its part of
the logout: the session invalidated, the cookies cleared, the browser's data
dropped, the caller redirected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_security_http import ClearedCookie

__all__ = ["LogoutConfig"]


def _no_cookies() -> dict[str, ClearedCookie]:
    """The empty cookie mapping a logout configuration starts with."""
    return {}


@dataclass(frozen=True, slots=True)
class LogoutConfig:
    """How a firewall's requests log out.

    Attributes:
        path: The path a request asks for a logout by.
        target_path: Where an unanswered logout redirects to — the home path
            by default.
        enable_csrf: Whether a logout request must prove itself with a
            cross-site request forgery token. A logout acts on the caller's
            behalf, so a firewall reachable from a browser should ask for
            the proof.
        csrf_parameter: The name the request carries the forgery token under,
            in its submitted form or its query string.
        csrf_token_id: The id the forgery token is stored under.
        clear_site_data: The directives the ``Clear-Site-Data`` header
            carries on the logout's response — ``"*"`` or a subset of the
            directive names — or ``None`` for no header.
        cookie_clearing: Each cookie a logout clears, mapped to the
            attributes it was set with.
        invalidate_session: Whether the logout invalidates the session the
            request reattached. Meaningful on a stateful firewall only.
        clear_csrf_tokens: Whether the logout drops every forgery token the
            request's session minted.

    Raises:
        InvalidConfigurationError: When a path is empty, or the site-data
            directives are.
    """

    path: str = "/logout"
    target_path: str = "/"
    enable_csrf: bool = False
    csrf_parameter: str = "_csrf_token"
    csrf_token_id: str = "logout"  # noqa: S105 -- the default id of the logout's forgery token, not a credential
    clear_site_data: Sequence[str] | None = None
    cookie_clearing: Mapping[str, ClearedCookie] = field(default_factory=_no_cookies)
    invalidate_session: bool = True
    clear_csrf_tokens: bool = False

    def __post_init__(self) -> None:
        """Check the paths and the directives are there to be read.

        Raises:
            InvalidConfigurationError: When a path is empty, or the site-data
                directives are.
        """
        if not self.path:
            raise InvalidConfigurationError("A logout needs the path it is asked for by.")
        if not self.target_path:
            raise InvalidConfigurationError("A logout needs the path it redirects to.")
        if self.clear_site_data is not None and not self.clear_site_data:
            raise InvalidConfigurationError(
                "The logout's clear_site_data names no directive; "
                'set ("*",) to clear everything, or None for no header.',
            )
