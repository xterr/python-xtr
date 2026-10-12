"""Reading the token an incoming request presents, and judging it.

A resource server does nothing with a request until it knows whose token it
carries. That reading is kept apart from the server itself so a deployment can
replace it — a different scheme, a different profile of token — without
touching anything that sits on top.

- :class:`AuthorizationValidatorInterface` — what a resource server reads
  through.
- :class:`BearerTokenValidatorInterface` — what judges one access token.
- :class:`BearerTokenValidator` — the shipped reading of RFC 6750's ``Bearer``
  scheme and RFC 9068's access-token profile.
"""

from __future__ import annotations

from .authorization_validator_interface import AuthorizationValidatorInterface
from .bearer_token_validator import BearerTokenValidator
from .bearer_token_validator_interface import BearerTokenValidatorInterface

__all__ = [
    "AuthorizationValidatorInterface",
    "BearerTokenValidator",
    "BearerTokenValidatorInterface",
]
