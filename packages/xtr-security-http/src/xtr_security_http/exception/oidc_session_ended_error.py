"""An OIDC provider ended the session a login belongs to."""

from __future__ import annotations

from typing import ClassVar

from xtr_security_core.exception import AuthenticationError

__all__ = ["OidcSessionEndedError"]


class OidcSessionEndedError(AuthenticationError):
    """The reason a login is deauthenticated when a back-channel logout ended its provider session.

    The session is not invalidated, as it can hold the logins of other
    firewalls. An application that wants it invalidated — the way a
    front-channel logout does by default — does it from the deauthentication
    event, by reading this error off the reason the event carries.
    """

    MESSAGE_KEY: ClassVar[str] = "The OIDC provider ended the session this login belongs to."
