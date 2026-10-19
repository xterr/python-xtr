"""A logout was asked for and could not be carried out."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

__all__ = ["LogoutError"]


class LogoutError(SecurityError, RuntimeError):
    """A request reached the logout step and failed its proof.

    Also a :class:`RuntimeError`. The one cause today is a cross-site
    request forgery token that does not check out: a request that names
    the logout path must still prove it came from a page the application
    rendered, and one that cannot is refused rather than logged out.
    """
