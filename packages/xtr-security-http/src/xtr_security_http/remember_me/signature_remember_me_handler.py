"""The remember-me handler that signs its cookies, and stores nothing."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import (
    AuthenticationError,
    ExpiredSignatureError,
    InvalidSignatureError,
)

from ._clock import system_now
from .abstract_remember_me_handler import AbstractRememberMeHandler
from .remember_me_details import RememberMeDetails

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.signature.signature_hasher import SignatureHasher
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

__all__ = ["SignatureRememberMeHandler"]


@final
class SignatureRememberMeHandler(AbstractRememberMeHandler):
    """Signs the cookie's value, so the cookie vouches for itself.

    The cookie's value is a signature over the user, the expiry and the
    user's covered fields — checked against the identifier before the user
    is even loaded, then against the loaded user's own fields, so a changed
    password retires every cookie issued before it. Nothing is stored: no
    series, no token value, which is also the limit — a single cookie cannot
    be revoked alone, only every cookie of the user, by changing what the
    signature covers. A handler that must revoke one login reaches for the
    persistent one instead.

    A consumed cookie is reissued: the login it re-establishes stages a
    fresh cookie, signed until a new expiry, so a remembered session carries
    on without the user ever seeing a login page.
    """

    __slots__: tuple[str, ...] = ("_clock", "_signature_hasher")

    def __init__(
        self,
        signature_hasher: SignatureHasher,
        user_provider: UserProviderInterface,
        options: Mapping[str, object] | None = None,
        logger: LoggerInterface | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Record the hasher, the provider, the options and the clock.

        Args:
            signature_hasher: Signs the cookie's value and checks it — the
                same hasher the login links use, bound to the user's covered
                fields.
            user_provider: Loads the user a cookie names.
            options: The cookie's shape, merged over the defaults.
            logger: Where the flow's decisions are logged, or ``None``.
            clock: Reads the current instant, for the expiry each new cookie
                is signed until; the system clock when ``None``.
        """
        super().__init__(user_provider, options, logger)
        self._signature_hasher = signature_hasher
        self._clock = clock if clock is not None else system_now

    @override
    async def create_remember_me_cookie(
        self,
        request: ServerRequestInterface,
        user: UserInterface,
    ) -> None:
        """Stage a cookie signed for ``user``, until a lifetime from now."""
        expires = int(self._clock().timestamp()) + self._lifetime()
        value = self._signature_hasher.compute_signature_hash(user, expires)
        self._create_cookie(request, RememberMeDetails(user.get_user_identifier(), expires, value))

    @override
    async def consume_remember_me_cookie(
        self,
        request: ServerRequestInterface,
        remember_me_details: RememberMeDetails,
    ) -> UserInterface:
        """Check the signature against the identifier, then against the user.

        The first check — the HMAC alone, before the user is loaded — keeps
        an unproven cookie from costing a user lookup; the second, in
        :meth:`process_remember_me`, weighs the covered fields once the user
        is there to be weighed.

        Raises:
            AuthenticationError: When the signature matches neither the
                identifier nor any secret, or the expiry has passed.
        """
        try:
            self._signature_hasher.accept_signature_hash(
                remember_me_details.get_user_identifier(),
                remember_me_details.get_expires(),
                remember_me_details.get_value(),
            )
        except InvalidSignatureError as error:
            raise AuthenticationError("The cookie's hash is invalid.") from error
        except ExpiredSignatureError as error:
            raise AuthenticationError("The cookie has expired.") from error
        return await super().consume_remember_me_cookie(request, remember_me_details)

    @override
    async def process_remember_me(
        self,
        request: ServerRequestInterface,
        remember_me_details: RememberMeDetails,
        user: UserInterface,
    ) -> None:
        """Verify the signature against the loaded user, then reissue the cookie.

        Raises:
            AuthenticationError: When the covered fields no longer add up to
                the signed value — a changed password — or the expiry has
                passed.
        """
        try:
            self._signature_hasher.verify_signature_hash(
                user,
                remember_me_details.get_expires(),
                remember_me_details.get_value(),
            )
        except InvalidSignatureError as error:
            raise AuthenticationError("The cookie's hash is invalid.") from error
        except ExpiredSignatureError as error:
            raise AuthenticationError("The cookie has expired.") from error
        await self.create_remember_me_cookie(request, user)
