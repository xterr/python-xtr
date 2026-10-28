"""A login link was presented that does not check out."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

from .invalid_login_link_error_interface import InvalidLoginLinkErrorInterface

__all__ = ["InvalidLoginLinkError"]


class InvalidLoginLinkError(SecurityError, RuntimeError, InvalidLoginLinkErrorInterface):
    """A request presented a login link the handler cannot accept.

    The link's own reading failed — a parameter missing or malformed, a
    hash that verifies under no secret, a user the provider does not
    know — before any authentication ran; the error names the link, not
    a login attempt. The authentication layer's answer to it is
    :class:`~xtr_security_http.exception.InvalidLoginLinkAuthenticationError`.
    """
