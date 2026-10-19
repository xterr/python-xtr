"""An OIDC provider answered a token request with ``invalid_grant``."""

from __future__ import annotations

from typing import ClassVar

from xtr_security_core.exception import AuthenticationError

__all__ = ["OidcInvalidGrantError"]


class OidcInvalidGrantError(AuthenticationError):
    """An OIDC provider no longer honors a grant, for good.

    The one token endpoint error of RFC 6749, Section 5.2 a caller has to tell
    apart from every other failure: the grant is gone for good — the refresh
    token expired, was revoked, or was issued to another client — where an
    unreachable provider or a server error only means the request may be
    tried again. A caller that catches this knows not to.
    """

    MESSAGE_KEY: ClassVar[str] = "The OIDC provider rejected the grant."
