"""The keys the security flow reads and writes on a request.

Two families, one rule each. What an application may read — the username
a login form re-fills, the error an error page explains, the path a login
was heading for — carries the ``_security.`` spelling the security layer's
documentation and recipes use, so a template or a view written against
it keeps working. What only the flow itself reads — the per-request
carrier and the handoffs between its steps — carries the
``_xtr_security_`` prefix, so it never collides with what an application
keeps on the same bag or session.
"""

from __future__ import annotations

from typing import Final, final

__all__ = ["SecurityRequestAttributes"]


@final
class SecurityRequestAttributes:
    """Every key the security flow parks on a request's state bag or session.

    The flow's steps hand each other what they learned through these keys —
    the carrier holding the request's security state, the authenticators a
    supports pass chose, the cookie a handler staged before a response
    existed — and the user-facing edges of a login keep what a form or an
    error page reads under the ``_security.`` spelling. One class holds
    them all so no step invents its own key and no two steps disagree
    about one.
    """

    ACCESS_DENIED_ERROR: Final[str] = "_security.403_error"
    """The access-denied error of the request, kept for the error page that
    explains the denial."""

    AUTHENTICATION_ERROR: Final[str] = "_security.last_error"
    """The last authentication error, kept for the page that answers a
    failed login."""

    LAST_USERNAME: Final[str] = "_security.last_username"
    """The username the last login attempt carried, for the form to re-fill."""

    UNSUPPORTED_REASONS: Final[str] = "_security.unsupported_reasons"
    """Why each authenticator did not support the request, collected while
    the supports pass runs and read by the tooling that explains a
    firewall's decision."""

    RE_AUTHENTICATION_ATTRIBUTE: Final[str] = "_security.re_authentication_attribute"
    """The security attribute a re-authentication was started for, so an
    entry point asking its question in several ways knows which one was
    asked here."""

    TARGET_PATH: Final[str] = "_security.{firewall}.target_path"
    """The session key a login saves the path it interrupted under, formatted
    with the firewall's name — the page the flow returns the user to once
    they have authenticated."""

    SECURITY_STATE: Final[str] = "_xtr_security_"
    """The per-request carrier of the flow's state, parked on the request's
    state bag; everything the flow learns about one request gathers under
    this one key."""

    STATE_BAG: Final[str] = "_xtr_security_state_bag"
    """The kernel event's state bag, parked on the request a firewall chain's
    caller hands to a listener's ``supports`` — the same bag the event
    carries, so a listener asked from the request alone and one asked from
    the event derive one carrier per request."""

    EXCEPTION_LISTENER: Final[str] = "_xtr_security_exception_listener"
    """The exception listener of the request's matched firewall, handed from
    the request phase that ran the chain to the exception phase that answers
    the request's failure, and put away when the request finishes."""

    AUTHENTICATORS: Final[str] = "_xtr_security_authenticators"
    """The authenticators that supported the request, handed from the pass
    that asks to the pass that authenticates."""

    SKIPPED_AUTHENTICATORS: Final[str] = "_xtr_security_skipped_authenticators"
    """The authenticators that did not support the request, kept for the
    tooling that explains a firewall's decision."""

    ACCESS_CONTROL_ATTRIBUTES: Final[str] = "_xtr_security_access_control_attributes"
    """The security attributes the matched access rule requires, handed from
    the pass that matches to the pass that decides."""

    FIREWALL_RUN: Final[str] = "_xtr_security_firewall_run"
    """Marks the requests the firewall actually ran for, so the response pass
    stores the context only for those."""

    PRE_AUTHENTICATED_USERNAME: Final[str] = "_xtr_security_pre_authenticated_username"
    """The username a pre-authenticated authenticator read from the request,
    handed from its supports pass to its authenticate pass."""

    LOGIN_LINK_PARAMETERS: Final[str] = "_xtr_security_login_link_parameters"
    """The extra parameters a consumed login link carried, exposed to the
    handlers that answer the login."""

    REMEMBER_ME_COOKIE: Final[str] = "_xtr_security_remember_me_cookie"
    """The remember-me cookie a handler staged on the request before a
    response existed, moved onto the response by the response pass."""
