"""Validating the claims of a logout token."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Final, final

from xtr_clock import SystemClock
from xtr_security_core.exception import AuthenticationError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface

__all__ = ["OidcLogoutToken"]

_MANDATORY_CLAIMS: Final = ("iss", "aud", "iat", "exp", "jti", "events")
"""The claims OpenID Connect Back-Channel Logout 1.0, Section 2.4 makes
mandatory in a logout token."""


@final
class OidcLogoutToken:
    """Validates the claims of a logout token, the security event token of RFC 8417.

    A provider pushes one to say that one of its sessions ended. The
    signature is not verified here: the token arrives unauthenticated, from
    anyone able to reach the back-channel logout endpoint, so it is the
    signature verifier that makes it the provider's, and that check can
    never be skipped.
    """

    __slots__ = ("_allowed_time_drift", "_clock")

    EVENT: Final = "http://schemas.openid.net/event/backchannel-logout"
    """The one member the ``events`` claim must carry, OpenID Connect
    Back-Channel Logout 1.0, Section 2.4: it is what tells a logout token
    from any other security event token."""

    def __init__(
        self,
        clock: ClockInterface | None = None,
        allowed_time_drift: int = 0,
    ) -> None:
        """Record the clock the time claims are read on, and the drift allowed on them.

        Args:
            clock: What the time claims are confronted with.
            allowed_time_drift: The tolerance, in seconds, on the ``exp``
                and ``iat`` claims.
        """
        self._clock = clock if clock is not None else SystemClock()
        self._allowed_time_drift = allowed_time_drift

    def validate_claims(
        self,
        claims: Mapping[str, object],
        expected_issuer: str,
        expected_audience: str,
    ) -> str:
        """Validate logout token claims per OpenID Connect Back-Channel Logout 1.0, Section 2.6.

        A token carrying a ``sub`` and no ``sid`` names an end-user rather
        than a session, which is what ``backchannel_logout_session_required``
        is registered with the provider to prevent: this client holds
        sessions, so it is told which one ended, and a token that does not
        say is refused rather than logging every session of that user out.

        ``exp`` is required and checked, Section 2.4 listing it as such and
        Section 2.6 asking for it to be validated the way an ID token is. It
        is what bounds a captured token: Section 2.6 leaves remembering
        ``jti`` optional, so nothing else here would refuse a replay once the
        session it names is no longer the one being presented.

        Args:
            claims: The decoded claims of the logout token.
            expected_issuer: The issuer the token must name.
            expected_audience: The client the token must be intended for.

        Returns:
            The ``sid`` claim, the provider session whose end the token
            announces.

        Raises:
            AuthenticationError: When any claim validation fails.
        """
        missing = [name for name in _MANDATORY_CLAIMS if claims.get(name) is None]
        if missing:
            absent = ", ".join(f'"{name}"' for name in missing)
            raise AuthenticationError(
                f"Invalid logout token: the mandatory claim(s) {absent} are missing.",
            )
        issuer = claims["iss"]
        if not isinstance(issuer, str) or issuer != expected_issuer:
            raise AuthenticationError(
                f'Invalid logout token: the issuer "{issuer}" does not match the '
                f'expected "{expected_issuer}".',
            )
        if not _names_audience(claims["aud"], expected_audience):
            raise AuthenticationError(
                f'Invalid logout token: the audience does not name "{expected_audience}".',
            )
        now = int(self._clock.now().timestamp())
        drift = self._allowed_time_drift
        _check_time_claims(claims, now, drift)
        # Section 2.4: a logout token carries no "nonce", and Section 2.6 has
        # the client check it, which is what keeps an ID token from being
        # replayed as a logout token.
        if "nonce" in claims:
            raise AuthenticationError(
                'Invalid logout token: it carries a "nonce" claim, which only an ID token does.',
            )
        events = claims["events"]
        if (
            not isinstance(events, dict)
            or self.EVENT not in events
            or not isinstance(events[self.EVENT], dict)
        ):
            raise AuthenticationError(
                f'Invalid logout token: the "events" claim must be an object carrying the '
                f'"{self.EVENT}" member.',
            )
        sid = claims.get("sid")
        if not isinstance(sid, str) or not sid:
            raise AuthenticationError(
                'Invalid logout token: the "sid" claim must be a non-empty string naming '
                "the session that ended.",
            )
        return sid


def _check_time_claims(
    claims: Mapping[str, object],
    now: int,
    drift: int,
) -> None:
    """Confront the ``exp`` and ``iat`` claims with ``now``.

    Both claims are mandatory, so a claim that names no instant is refused
    rather than skipped. ``nbf`` is not read: a security event token carries
    none, and a logout token is not valid-yet-checked.

    Raises:
        AuthenticationError: When the token has expired, or was issued in
            the future.
    """
    exp = _timestamp(claims["exp"])
    if exp is None:
        raise AuthenticationError('Invalid logout token: the "exp" claim is not a timestamp.')
    if exp < now - drift:
        raise AuthenticationError("Invalid logout token: the token has expired.")
    iat = _timestamp(claims["iat"])
    if iat is None:
        raise AuthenticationError('Invalid logout token: the "iat" claim is not a timestamp.')
    if iat > now + drift:
        raise AuthenticationError("Invalid logout token: the token was issued in the future.")


def _names_audience(audience: object, expected: str) -> bool:
    """Tell whether an ``aud`` claim names ``expected``.

    The claim is a string or a list of strings, and a single match is
    enough: a token minted for several audiences is meant for each of them.
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
