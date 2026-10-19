"""The remember-me handler that stores its tokens, and can revoke one login."""

from __future__ import annotations

import base64
import hmac
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.authentication.remember_me.persistent_token import PersistentToken
from xtr_security_core.authentication.remember_me.token_verifier_interface import (
    TokenVerifierInterface,
)
from xtr_security_core.exception import (
    AuthenticationError,
    CookieTheftError,
)

from ._clock import system_now
from ._signature_digest import digest_of, properties_digest, with_digest
from .abstract_remember_me_handler import AbstractRememberMeHandler
from .remember_me_details import RememberMeDetails

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.remember_me.token_provider_interface import (
        TokenProviderInterface,
    )
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

__all__ = ["PersistentRememberMeHandler"]

#: The base64 spelling a cookie value carries: the characters a value may not
#: hold, written as the ones it may.
_ENCODE_ALPHABET = str.maketrans("+/=", "-_~")

#: How long after its last use a stored value is still rotated. A value
#: presented twice within the window is the same request arriving twice —
#: tabs opened together, a page loading in parallel — not a theft, and
#: rotating it for each would spend it under the others.
_ROTATION_WINDOW = 60


@final
class PersistentRememberMeHandler(AbstractRememberMeHandler):
    """Stores every cookie's series and value, so one login can be revoked.

    Each cookie carries a series — the login it belongs to — and a value,
    both 33 random bytes in the cookie's alphabet, and the store keeps the
    one value the series expects next. A presented value that matches is
    spent on the spot: a fresh one is stored and staged for the response, so
    a stolen copy of the old cookie finds nothing left to present. A value
    that does not match was already spent — the cookie was copied, and the
    whole series is dropped so the thief and the owner are both logged out.

    The value also carries a digest of the user's signature properties — the
    password by default — so a changed password retires the series even
    though its random parts never changed. Properties the user does not
    expose are skipped while the list is the default one, which keeps a user
    class without any of them working as before.

    A store that can afford it may accept a slightly outdated value — the
    rotation window — through a verifier, so a request that raced its own
    rotation still logs in.
    """

    __slots__: tuple[str, ...] = (
        "_clock",
        "_signature_properties",
        "_token_provider",
        "_token_verifier",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- the handler's full shape: what stores, who loads, what is bound, how it is shaped
        self,
        token_provider: TokenProviderInterface,
        user_provider: UserProviderInterface,
        options: Mapping[str, object] | None = None,
        logger: LoggerInterface | None = None,
        token_verifier: TokenVerifierInterface | None = None,
        signature_properties: Sequence[str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Record the store, the provider, the bound properties and the clock.

        Args:
            token_provider: Keeps every series' current value — a database
                in an application, reached over I/O.
            user_provider: Loads the user a cookie names.
            options: The cookie's shape, merged over the defaults.
            logger: Where the flow's decisions are logged, or ``None``.
            token_verifier: Accepts a presented value the store no longer
                holds exactly — the rotation window's policy — and records a
                rotation without spending one; the provider itself when it
                implements the verifier's contract, and ``None`` for the
                plain equality.
            signature_properties: The user properties whose digest the value
                carries, retiring the series when any of them changes; the
                password alone when ``None``, skipping the properties the
                user does not expose.
            clock: Reads the current instant, for the expiry and the
                rotation window; the system clock when ``None``.
        """
        super().__init__(user_provider, options, logger)
        self._token_provider = token_provider
        self._token_verifier = token_verifier
        if self._token_verifier is None and isinstance(token_provider, TokenVerifierInterface):
            self._token_verifier = token_provider
        self._signature_properties = (
            None if signature_properties is None else tuple(signature_properties)
        )
        self._clock = clock if clock is not None else system_now

    @override
    async def create_remember_me_cookie(
        self,
        request: ServerRequestInterface,
        user: UserInterface,
    ) -> None:
        """Start a new series for ``user``, and stage its first cookie.

        The series and the value are one draw of randomness split in two —
        33 bytes each, the length the store's column was sized around — so
        neither can be derived from the other.
        """
        drawn = secrets.token_bytes(66)
        token_value = _encode(drawn[33:])
        series = _encode(drawn[:33])
        digest = properties_digest(user, self._signature_properties)
        if digest is not None:
            token_value = with_digest(token_value, digest)
        last_used = self._clock()
        token = PersistentToken(user.get_user_identifier(), series, token_value, last_used)
        await self._token_provider.create_new_token(token)
        self._create_cookie(
            request,
            RememberMeDetails.from_persistent_token(
                token,
                int(self._clock().timestamp()) + self._lifetime(),
            ),
        )

    @override
    async def consume_remember_me_cookie(
        self,
        request: ServerRequestInterface,
        remember_me_details: RememberMeDetails,
    ) -> UserInterface:
        """Check the presented value against the stored one, and hand the rest on.

        The details the cookie carried stop being trusted the moment the
        stored token is read: everything the check needs comes from the
        store, and the details handed on are rebuilt from the stored token —
        the last use, the series and the value the rotation will spend.

        Raises:
            AuthenticationError: When the value is not a series and a value,
                when the stored token names another user, or when the series
                has not been used within its lifetime.
            CookieTheftError: When the presented value was already spent —
                the cookie was copied, and the caller must be logged out
                with the thief.
        """
        value = remember_me_details.get_value()
        if ":" not in value:
            raise AuthenticationError("The cookie is incorrectly formatted.")
        series, _, token_value = value.partition(":")
        token = await self._token_provider.load_token_by_series(series)
        if token.get_user_identifier() != remember_me_details.get_user_identifier():
            raise AuthenticationError("The cookie's hash is invalid.")
        if self._token_verifier is not None:
            is_token_valid = await self._token_verifier.verify_token(token, token_value)
        else:
            is_token_valid = hmac.compare_digest(token.get_token_value(), token_value)
        if not is_token_valid:
            raise CookieTheftError(
                "This token was already used. The account is possibly compromised.",
            )
        expires = int(token.get_last_used().timestamp()) + self._lifetime()
        if expires < int(self._clock().timestamp()):
            raise AuthenticationError("The cookie has expired.")
        return await super().consume_remember_me_cookie(
            request,
            RememberMeDetails(
                token.get_user_identifier(),
                expires,
                f"{int(token.get_last_used().timestamp())}:{series}:{token.get_token_value()}:",
            ),
        )

    @override
    async def process_remember_me(
        self,
        request: ServerRequestInterface,
        remember_me_details: RememberMeDetails,
        user: UserInterface,
    ) -> None:
        """Rotate the stored value, unless the rotation window still holds.

        The value the details carry is the one the consume rebuilt from the
        store: when the user was last seen, the series, and the value that
        was current. A rotation within the window changes nothing — the
        concurrent requests that raced one another keep the value they all
        presented. Past the window, a fresh value is drawn, the digest of
        the user's signature properties is bound to it, the store rotates,
        and the fresh cookie is staged for the response.

        Raises:
            AuthenticationError: When the digest the value carries no
                longer matches the user — a changed password.
        """
        last_used, series, token_value, _user_class = remember_me_details.get_value().split(":", 3)
        token = PersistentToken(
            remember_me_details.get_user_identifier(),
            series,
            token_value,
            datetime.fromtimestamp(int(last_used), UTC),
        )
        digest = properties_digest(user, self._signature_properties)
        stored_digest = digest_of(token_value)
        if stored_digest is not None and (
            digest is None or not hmac.compare_digest(stored_digest, digest)
        ):
            raise AuthenticationError("The cookie's hash is invalid.")
        last_rotated_at = int(token.get_last_used().timestamp()) + _ROTATION_WINDOW
        if last_rotated_at >= int(self._clock().timestamp()):
            return
        token_value = _encode(secrets.token_bytes(33))
        if digest is not None:
            token_value = with_digest(token_value, digest)
        token_last_used = self._clock()
        if self._token_verifier is not None:
            await self._token_verifier.update_existing_token(token, token_value, token_last_used)
        await self._token_provider.update_token(series, token_value, token_last_used)
        self._create_cookie(request, remember_me_details.with_value(f"{series}:{token_value}"))

    @override
    async def clear_remember_me_cookie(self, request: ServerRequestInterface) -> None:
        """Clear the cookie, and drop the series the request presented.

        The cookie the request itself carries names the series being left —
        a logout knows which login it ends by the cookie it drops. A cookie
        too malformed to read is ignored: the clearing must not fail the
        response over a value nobody wrote.
        """
        await super().clear_remember_me_cookie(request)
        raw = request.get_cookie_params().get(str(self._options["name"]))
        if raw is None:
            return
        try:
            details = RememberMeDetails.from_raw_cookie(raw)
        except AuthenticationError:
            # A malformed cookie was not written by this flow; there is no
            # series it could name, and the response must not fail over it.
            return
        series = details.get_value().partition(":")[0]
        await self._token_provider.delete_token_by_series(series)


def _encode(raw: bytes) -> str:
    """Base64 ``raw`` in the alphabet a cookie value carries."""
    return base64.b64encode(raw).decode("ascii").translate(_ENCODE_ALPHABET)
