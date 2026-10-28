"""Decoding and validating the claims of an OIDC ID token."""

from __future__ import annotations

import hmac
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final, cast, final

from xtr_clock import SystemClock
from xtr_security_core.exception import AuthenticationError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface

__all__ = ["OidcIdToken"]

_MANDATORY_CLAIMS: Final = ("iss", "aud", "exp", "iat", "sub")
"""The claims OIDC Core 1.0, Section 3.1.3.7 makes mandatory in an ID token."""


@final
class OidcIdToken:
    """Decodes and validates OIDC ID tokens.

    The signature is not verified here: that is the job of
    :class:`~xtr_security_http.oidc.oidc_signature_verifier.OidcSignatureVerifier`,
    which the ``oidc_login`` authenticator uses by default, and which a token
    received directly from the token endpoint over TLS may do without (OIDC
    Core 1.0, Section 3.1.3.7, item 6).
    """

    __slots__ = ("_allowed_time_drift", "_clock")

    def __init__(
        self,
        clock: ClockInterface | None = None,
        allowed_time_drift: int = 0,
    ) -> None:
        """Record the clock the time claims are read on, and the drift allowed on them.

        Args:
            clock: What the time claims are confronted with.
            allowed_time_drift: The tolerance, in seconds, on the ``exp``,
                ``iat`` and ``nbf`` claims.
        """
        self._clock = clock if clock is not None else SystemClock()
        self._allowed_time_drift = allowed_time_drift

    async def decode(self, token: str) -> dict[str, object]:
        """Decode the claims of a JWT without verifying its signature.

        Returns:
            The decoded claims.

        Raises:
            AuthenticationError: When the token is not a readable compact JWT.
        """
        from joserfc import jws  # noqa: PLC0415 -- guarded behind the oidc extra

        try:
            payload = jws.extract_compact(token.encode()).payload
        except Exception as error:
            raise AuthenticationError("Invalid ID token format.") from error
        try:
            claims = cast("object", json.loads(payload or b""))
        except ValueError as error:
            raise AuthenticationError("Invalid ID token payload.") from error
        if not isinstance(claims, dict):
            raise AuthenticationError("Invalid ID token payload.")
        return cast("dict[str, object]", claims)

    def validate_claims(
        self,
        claims: Mapping[str, object],
        expected_issuer: str,
        expected_audience: str,
        expected_nonce: str | None = None,
        max_age: int | None = None,
    ) -> None:
        """Validate ID token claims per OIDC Core 1.0, Section 3.1.3.7.

        Args:
            claims: The decoded claims of the ID token.
            expected_issuer: The issuer the token must name.
            expected_audience: The client the token must be intended for.
            expected_nonce: The nonce the authorization request sent, when
                one was, that the token must repeat.
            max_age: The number of seconds since the authentication the
                token's ``auth_time`` must not exceed.

        Raises:
            AuthenticationError: When any claim validation fails.
        """
        missing = [name for name in _MANDATORY_CLAIMS if claims.get(name) is None]
        if missing:
            absent = ", ".join(f'"{name}"' for name in missing)
            raise AuthenticationError(
                f"Invalid ID token: the mandatory claim(s) {absent} are missing.",
            )
        issuer = claims["iss"]
        if not isinstance(issuer, str) or issuer != expected_issuer:
            raise AuthenticationError(
                f'Invalid ID token: the issuer "{issuer}" does not match the '
                f'expected "{expected_issuer}".',
            )
        if not _names_audience(claims["aud"], expected_audience):
            raise AuthenticationError(
                f'Invalid ID token: the audience does not name "{expected_audience}".',
            )
        now = int(self._clock.now().timestamp())
        drift = self._allowed_time_drift
        _check_time_claims(claims, now, drift)
        # "sub" is REQUIRED by OIDC Core 1.0, Section 2 and is the identity the
        # whole login is about; it is checked here rather than by the caller so
        # that a token missing it is rejected before its access token is put to
        # any use, the UserInfo request included.
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError(
                'Invalid ID token: the "sub" claim must be a non-empty string.',
            )
        # "azp" is only checked when present: OIDC Core 1.0, Section 3.1.3.7
        # items 3 to 5 are SHOULD, and the audience check above already ensures
        # the client_id is one of the audiences.
        authorized_party = claims.get("azp")
        if authorized_party is not None and not hmac.compare_digest(
            expected_audience,
            str(authorized_party),
        ):
            raise AuthenticationError(
                'ID token "azp" claim does not match the expected client_id.',
            )
        if expected_nonce is not None:
            nonce = claims.get("nonce")
            if nonce is None or not hmac.compare_digest(expected_nonce, str(nonce)):
                raise AuthenticationError("ID token nonce does not match.")
        if max_age is None:
            return
        _check_max_age(claims, now, max_age, self._allowed_time_drift)


def _check_time_claims(
    claims: Mapping[str, object],
    now: int,
    drift: int,
) -> None:
    """Confront the ``exp``, ``iat`` and ``nbf`` claims with ``now``.

    The ``exp`` and ``iat`` claims are mandatory, so a claim that names no
    instant is refused rather than skipped; ``nbf`` is optional, and absent
    means nothing to check.

    Raises:
        AuthenticationError: When the token has expired, was issued in the
            future, or is not valid yet.
    """
    exp = _timestamp(claims["exp"])
    if exp is None:
        raise AuthenticationError('Invalid ID token: the "exp" claim is not a timestamp.')
    if exp < now - drift:
        raise AuthenticationError("Invalid ID token: the token has expired.")
    iat = _timestamp(claims["iat"])
    if iat is None:
        raise AuthenticationError('Invalid ID token: the "iat" claim is not a timestamp.')
    if iat > now + drift:
        raise AuthenticationError("Invalid ID token: the token was issued in the future.")
    nbf = _timestamp(claims.get("nbf"))
    if nbf is not None and nbf > now + drift:
        raise AuthenticationError("Invalid ID token: the token is not valid yet.")


def _check_max_age(claims: Mapping[str, object], now: int, max_age: int, drift: int) -> None:
    """Confront the ``auth_time`` claim with the requested ``max_age``.

    OIDC Core 1.0, Section 3.1.2.1 makes ``auth_time`` the claim the request
    of a ``max_age`` turns mandatory, so a token without it — or with one
    that names no instant — is refused, and the authentication it dates is
    required to be recent enough.

    Raises:
        AuthenticationError: When the ``auth_time`` claim is missing, or
            dates an authentication older than the requested ``max_age``.
    """
    auth_time = _timestamp(claims.get("auth_time"))
    if auth_time is None:
        raise AuthenticationError(
            'ID token is missing the "auth_time" claim required when "max_age" is requested.',
        )
    if now - auth_time > max_age + drift:
        raise AuthenticationError(
            'ID token "auth_time" exceeds the requested "max_age"; re-authentication is required.',
        )


def _names_audience(audience: object, expected: str) -> bool:
    """Tell whether an ``aud`` claim names ``expected``.

    The claim is a string or a list of strings, and a single match is enough:
    a token minted for several audiences is meant for each of them.
    """
    if isinstance(audience, str):
        return audience == expected
    if isinstance(audience, Sequence):
        return expected in [one for one in audience if isinstance(one, str)]
    return False


def _timestamp(value: object) -> int | None:
    """Read a claim as a Unix timestamp, or ``None`` when it names no instant.

    A claim carrying anything but a number describes no instant a validation
    can confront a clock with, and is refused rather than honored.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)
