"""A login link was followed after the moment it was valid until."""

from __future__ import annotations

from xtr_security_core.exception import ExpiredSignatureError

from .invalid_login_link_error_interface import InvalidLoginLinkErrorInterface

__all__ = ["ExpiredLoginLinkError"]


class ExpiredLoginLinkError(ExpiredSignatureError, InvalidLoginLinkErrorInterface):
    """A login link whose hash is sound but whose moment has passed.

    Derives from the core's expired-signature error — a link's hash is a
    signature, and everything the core says about one past its expiry
    holds here — wearing the marker so the flow that refused the link
    catches it with the rest.
    """
