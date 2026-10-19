"""The authentication error a login link that does not check out becomes."""

from __future__ import annotations

from typing import ClassVar

from xtr_security_core.exception import AuthenticationError

__all__ = ["InvalidLoginLinkAuthenticationError"]


class InvalidLoginLinkAuthenticationError(AuthenticationError):
    """A login through a link failed because the link does not check out.

    The flow's one authentication-layer answer to every refusal the
    handler raises: the caller learns the link was invalid or expired,
    and nothing else — which parameter failed the link's reading stays in
    the error the handler already raised.
    """

    MESSAGE_KEY: ClassVar[str] = "Invalid or expired login link."
