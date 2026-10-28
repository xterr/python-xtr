"""How an OAuth2 client presents the access token it was issued.

Nothing here needs the JOSE library: a bearer token is presented as it is.
"""

from __future__ import annotations

from .access_token_type_interface import AccessTokenTypeInterface
from .bearer_token_type import BearerTokenType

__all__ = [
    "AccessTokenTypeInterface",
    "BearerTokenType",
]
