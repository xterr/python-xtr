"""What an ID token is signed with, and how long it lasts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import final

from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)

__all__ = ["IdTokenSettings"]

_NO_TIME = timedelta(0)


@final
@dataclass(frozen=True, slots=True)
class IdTokenSettings:
    """The two settings an ID token is minted with that its signer does not hold.

    The ID token is signed with the authorization server's own key, so a client
    verifies it against the key set the server already publishes. The signer
    holding that key does not say which algorithm it signs with, and the ID
    token has to say it twice — in its header, and in the digest its
    ``at_hash`` is computed with — so the algorithm is handed over here, the
    same one the server is configured to sign with.

    Attributes:
        algorithm: The signature algorithm the authorization server signs
            with, as its ``alg`` header names it.
        ttl: How long an ID token is good for, counted from when it is issued,
            or ``None`` to have it expire with the access token issued beside
            it.
    """

    algorithm: str
    ttl: timedelta | None = None

    def __post_init__(self) -> None:
        """Refuse settings no ID token could be minted with.

        Raises:
            InvalidArgumentError: When ``algorithm`` is empty, or ``ttl`` is set
                and not positive, which would mint a token already expired.
        """
        if self.algorithm == "":
            raise InvalidArgumentError(
                "algorithm names the signature algorithm the ID token is signed with and "
                "cannot be empty; pass the one the authorization server signs with.",
            )
        if self.ttl is not None and self.ttl <= _NO_TIME:
            raise InvalidArgumentError(
                f"ttl is how long an ID token is good for and must be positive; got {self.ttl}. "
                "Leave it unset to have the ID token expire with the access token.",
            )
