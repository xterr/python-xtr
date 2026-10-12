"""The errors this library raises, one family under one base.

Every error derives from :class:`OAuth2Error`, so one ``except OAuth2Error``
catches anything this library raises. The errors a firewall will have to answer
will also derive from the security family's ``AuthenticationError``, so the
family's handler will keep answering them.

- :class:`OAuth2Error` — the base of them all.
- :class:`InvalidConfigurationError` — a deployment's configuration the bundle
  cannot turn into a server, named setting by setting.
- :class:`InvalidArgumentError` — one of this library's own objects used
  wrongly, which is a caller's mistake and nobody's answer.
- :class:`OAuthServerError` — a refusal the protocol has a name for, and the
  answer that carries it.
- :class:`UniqueTokenIdentifierConstraintViolationError` — a token identifier
  that was already taken, which a grant retries past.
"""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .invalid_configuration_error import InvalidConfigurationError
from .oauth2_error import OAuth2Error
from .oauth_server_error import OAuthServerError
from .unique_token_identifier_constraint_violation_error import (
    UniqueTokenIdentifierConstraintViolationError,
)

__all__ = [
    "InvalidArgumentError",
    "InvalidConfigurationError",
    "OAuth2Error",
    "OAuthServerError",
    "UniqueTokenIdentifierConstraintViolationError",
]
