"""The remember-me suite: the cookie a login outlives, set, checked and cleared.

A login may be asked to outlive its session: the user ticks a box, and the
response carries a cookie that re-establishes them on their next visit. The
handlers here are the one voice on what that cookie holds — a signed value
that vouches for itself, or a stored series that can be revoked one login at
a time — and the pieces around them decide when it is wanted, move it onto
the response, and turn it back into a login when it returns.
"""

from __future__ import annotations

from .abstract_remember_me_handler import AbstractRememberMeHandler
from .persistent_remember_me_handler import PersistentRememberMeHandler
from .remember_me_cookie import RememberMeCookie
from .remember_me_details import RememberMeDetails
from .remember_me_handler_interface import RememberMeHandlerInterface
from .response_listener import ResponseListener
from .signature_remember_me_handler import SignatureRememberMeHandler

__all__ = [
    "AbstractRememberMeHandler",
    "PersistentRememberMeHandler",
    "RememberMeCookie",
    "RememberMeDetails",
    "RememberMeHandlerInterface",
    "ResponseListener",
    "SignatureRememberMeHandler",
]
