"""The collision raised when a freshly minted token identifier is already taken."""

from __future__ import annotations

from typing import Self, final

from .oauth_server_error import OAuthServerError

__all__ = ["UniqueTokenIdentifierConstraintViolationError"]


@final
class UniqueTokenIdentifierConstraintViolationError(OAuthServerError):
    """Storing a token failed because its identifier was already in use.

    A repository raises this when the identifier a grant generated collides
    with one already stored. It is the one error of this library that is
    normally never answered: a grant catches it and mints a new identifier,
    and only a run of collisions long enough to exhaust its retries lets it
    out — which is why it is a 500 rather than a refusal the client could do
    anything about.
    """

    @classmethod
    def create(cls) -> Self:
        """Report that no free identifier could be found."""
        return cls(
            "Could not create unique access token identifier", 100, "access_token_duplicate", 500
        )
