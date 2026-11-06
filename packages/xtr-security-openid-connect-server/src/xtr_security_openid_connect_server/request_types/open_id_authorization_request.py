"""The authorization request a sign-in carries across the consent step."""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server_core.request_types.authorization_request import AuthorizationRequest

from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)

__all__ = ["OpenIdAuthorizationRequest"]


@final
class OpenIdAuthorizationRequest(AuthorizationRequest):
    """An authorization request that is also a sign-in.

    The request is the one piece of state that crosses the consent step, so
    what the identity layer needs from the original request waits here while
    the resource owner decides: the ``nonce`` the ID token repeats back, the
    ``prompt`` and ``max_age`` that say whether the end-user has to sign in
    again first, and when they last did. Everything else is the shipped
    request's, and the grant goes on filling it in as it always did.

    Each of the four is absent until it is set, and absent means not asked
    for: no ``nonce`` to repeat, no ``prompt`` value, no limit on how old a
    sign-in may be, no known sign-in time.
    """

    __slots__ = ("_auth_time", "_max_age", "_nonce", "_prompt")

    def __init__(self) -> None:
        """Start an empty request, carrying nothing of a sign-in yet."""
        super().__init__()
        self._nonce: str | None = None
        self._prompt: frozenset[str] = frozenset()
        self._max_age: int | None = None
        self._auth_time: int | None = None

    def get_nonce(self) -> str | None:
        """Return the ``nonce`` the request carried, or ``None`` for none."""
        return self._nonce

    def set_nonce(self, nonce: str | None) -> None:
        """Record the ``nonce`` the request carried, for the ID token to repeat back."""
        self._nonce = nonce

    def get_prompt(self) -> frozenset[str]:
        """Return the ``prompt`` values the request carried, empty for none.

        A set rather than the parameter as it was sent: its values have no
        order, and what a reader asks is whether one of them is there.
        """
        return self._prompt

    def set_prompt(self, prompt: frozenset[str]) -> None:
        """Record the ``prompt`` values the request carried."""
        self._prompt = prompt

    def get_max_age(self) -> int | None:
        """Return how old a sign-in the request accepts, in seconds, or ``None`` for any."""
        return self._max_age

    def set_max_age(self, max_age: int | None) -> None:
        """Record the ``max_age`` the request carried, ``None`` for none.

        Zero is kept as an age like any other: it asks for a sign-in made just
        now.

        Raises:
            InvalidArgumentError: When ``max_age`` is negative, which is no age
                a sign-in can have.
        """
        if max_age is not None and max_age < 0:
            raise InvalidArgumentError(
                f"max_age is a number of seconds and cannot be negative; got {max_age}.",
            )
        self._max_age = max_age

    def get_auth_time(self) -> int | None:
        """Return when the end-user last signed in, in seconds since the epoch, or ``None``."""
        return self._auth_time

    def set_auth_time(self, auth_time: int | None) -> None:
        """Record when the end-user last signed in, ``None`` when that is not known."""
        self._auth_time = auth_time
