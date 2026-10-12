"""The errors this library raises, one family under one base.

Every error derives from :class:`OAuth2Error`, so one ``except OAuth2Error``
catches anything this library raises. The bundle that wires this library into an
application adds its own errors beside these, each deriving from the same base.

- :class:`OAuth2Error` — the base of them all.
- :class:`InvalidArgumentError` — one of this library's own objects used
  wrongly, which is a caller's mistake and nobody's answer.
- :class:`OAuthServerError` — a refusal the protocol has a name for, and the
  answer that carries it.
- :class:`UniqueTokenIdentifierConstraintViolationError` — a token identifier
  that was already taken, which a grant retries past.
"""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .oauth2_error import OAuth2Error
from .oauth_server_error import OAuthServerError
from .unique_token_identifier_constraint_violation_error import (
    UniqueTokenIdentifierConstraintViolationError,
)

__all__ = [
    "InvalidArgumentError",
    "OAuth2Error",
    "OAuthServerError",
    "UniqueTokenIdentifierConstraintViolationError",
]
