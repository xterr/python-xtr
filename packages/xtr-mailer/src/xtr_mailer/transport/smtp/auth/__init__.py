"""The ``AUTH`` mechanisms an ESMTP transport logs in with.

An :class:`AuthenticatorInterface` speaks one mechanism through the transport's session.
:class:`CramMd5Authenticator`, :class:`PlainAuthenticator`, :class:`LoginAuthenticator` and
:class:`XOAuth2Authenticator` are the ones an
:class:`~xtr_mailer.transport.smtp.EsmtpTransport` tries by default, in that order.
"""

from __future__ import annotations

from .authenticator_interface import AuthenticatorInterface
from .cram_md5_authenticator import CramMd5Authenticator
from .login_authenticator import LoginAuthenticator
from .plain_authenticator import PlainAuthenticator
from .x_o_auth2_authenticator import XOAuth2Authenticator

__all__ = [
    "AuthenticatorInterface",
    "CramMd5Authenticator",
    "LoginAuthenticator",
    "PlainAuthenticator",
    "XOAuth2Authenticator",
]
