"""The refusals the resource-server side answers a request with.

Both derive from the security family's ``AuthenticationError`` as well as from
this package's own base, so the firewall answers them while one ``except
OAuth2Error`` still catches everything from here.
"""

from __future__ import annotations

from .oauth2_authentication_error import OAuth2AuthenticationError
from .oauth2_authentication_failed_error import OAuth2AuthenticationFailedError

__all__ = [
    "OAuth2AuthenticationError",
    "OAuth2AuthenticationFailedError",
]
