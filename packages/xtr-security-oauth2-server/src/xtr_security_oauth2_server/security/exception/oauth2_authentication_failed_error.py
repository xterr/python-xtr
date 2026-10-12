"""The resource server read the access token and would not accept it."""

from __future__ import annotations

from http import HTTPStatus
from typing import ClassVar, Self

from .oauth2_authentication_error import OAuth2AuthenticationError

__all__ = ["OAuth2AuthenticationFailedError"]


class OAuth2AuthenticationFailedError(OAuth2AuthenticationError):
    """The one refusal the resource-server side actually raises.

    Whatever went wrong with the token — a signature that does not check out,
    an expiry that has passed, a withdrawal, an issuer that is not this server,
    a missing resource owner — arrives here as the same ``401``. That is
    deliberate: a caller presenting a token that will not work learns only
    that, because telling it *which* of those it was turns the endpoint into a
    way of probing what this server holds.

    The cause is kept, so a log shows which it was.
    """

    MESSAGE_KEY: ClassVar[str] = "The access token could not be accepted."

    @classmethod
    def create(cls, message: str, previous: BaseException | None = None) -> Self:
        """Refuse with ``401``, saying ``message`` internally and keeping ``previous``.

        Args:
            message: What went wrong, for a log and a traceback.
            previous: The error that led here — the protocol refusal the
                resource server raised — kept as the cause.

        Returns:
            The refusal, ready to raise.
        """
        error = cls(message, HTTPStatus.UNAUTHORIZED)
        if previous is not None:
            error.__cause__ = previous

        return error
