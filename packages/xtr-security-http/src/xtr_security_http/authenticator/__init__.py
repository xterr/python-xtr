"""The authenticators a firewall runs, and the passports they produce."""

from __future__ import annotations

from .abstract_authenticator import AbstractAuthenticator
from .abstract_login_form_authenticator import AbstractLoginFormAuthenticator
from .abstract_pre_authenticated_authenticator import AbstractPreAuthenticatedAuthenticator
from .access_token_authenticator import AccessTokenAuthenticator
from .authenticator_interface import AuthenticatorInterface
from .debug import (
    TraceableAuthenticator,
    TraceableAuthenticatorManagerListener,
    UnsupportedReasons,
)
from .fallback_user_loader import FallbackUserLoader
from .form_login_authenticator import FormLoginAuthenticator
from .http_basic_authenticator import HttpBasicAuthenticator
from .interactive_authenticator_interface import InteractiveAuthenticatorInterface
from .json_login_authenticator import JsonLoginAuthenticator
from .login_link_authenticator import LoginLinkAuthenticator
from .oidc_login_authenticator import OidcLoginAuthenticator
from .remember_me_authenticator import RememberMeAuthenticator
from .remote_user_authenticator import RemoteUserAuthenticator
from .x509_authenticator import X509Authenticator

__all__ = [
    "AbstractAuthenticator",
    "AbstractLoginFormAuthenticator",
    "AbstractPreAuthenticatedAuthenticator",
    "AccessTokenAuthenticator",
    "AuthenticatorInterface",
    "FallbackUserLoader",
    "FormLoginAuthenticator",
    "HttpBasicAuthenticator",
    "InteractiveAuthenticatorInterface",
    "JsonLoginAuthenticator",
    "LoginLinkAuthenticator",
    "OidcLoginAuthenticator",
    "RememberMeAuthenticator",
    "RemoteUserAuthenticator",
    "TraceableAuthenticator",
    "TraceableAuthenticatorManagerListener",
    "UnsupportedReasons",
    "X509Authenticator",
]
