"""A token read back, its signature checked and its times judged."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface

__all__ = ["EXPIRED", "INVALID", "VERIFIED", "LoadedJws"]

#: The token verified, and its times are in order.
VERIFIED: Final[str] = "verified"

#: The token verified, but its expiry has passed.
EXPIRED: Final[str] = "expired"

#: The token's times do not hold — a missing expiry, or an issued-at in the future.
INVALID: Final[str] = "invalid"


@final
class LoadedJws:
    """A token whose signature was checked, judged against its time claims.

    Built by a provider's ``load`` once it has decided whether the signature
    verifies. The state it settles on tells the encoder what to raise: a token
    whose issued-at lies in the future, whose not-before time has not yet been
    reached, or whose expiry is missing, is :data:`INVALID`; one past its expiry
    is :data:`EXPIRED`; otherwise it is :data:`VERIFIED`. An invalid time
    overrides a good signature, so the time is judged the moment the token is
    built. The configured clock skew widens every one of these windows.

    When the application allows tokens with no expiry, a token carrying none
    stands on its signature alone. An expiry it does carry is still judged: the
    allowance tolerates a missing ``exp``, never a lapsed one.

    Attributes:
        VERIFIED: The state of a token in order.
        EXPIRED: The state of a token past its expiry.
        INVALID: The state of a token whose times do not hold.
    """

    VERIFIED: Final[str] = VERIFIED
    EXPIRED: Final[str] = EXPIRED
    INVALID: Final[str] = INVALID

    __slots__ = (
        "_allow_no_expiration",
        "_clock",
        "_clock_skew",
        "_header",
        "_is_verified",
        "_payload",
        "_state",
    )

    def __init__(  # noqa: PLR0913 -- a value object; each part is a fact about the loaded token
        self,
        payload: Mapping[str, object],
        clock: ClockInterface,
        *,
        is_verified: bool,
        allow_no_expiration: bool = False,
        header: Mapping[str, object] | None = None,
        clock_skew: int = 0,
    ) -> None:
        """Record the token's parts and judge its times against ``clock``."""
        self._payload = dict(payload)
        self._is_verified = is_verified
        self._header = dict(header) if header is not None else {}
        self._clock = clock
        self._clock_skew = clock_skew
        self._allow_no_expiration = allow_no_expiration
        self._state = VERIFIED
        self._check_issued_at()
        self._check_not_before()
        self._check_expiration()

    def get_header(self) -> Mapping[str, object]:
        """Return the token's header parameters."""
        return self._header

    def get_payload(self) -> Mapping[str, object]:
        """Return the token's claims, as they were signed."""
        return self._payload

    def is_verified(self) -> bool:
        """Tell whether the signature verified against a known key."""
        return self._is_verified

    def is_expired(self) -> bool:
        """Tell whether the token is past its expiry, re-judging as time passes."""
        if self._state == VERIFIED:
            self._check_expiration()
        return self._state == EXPIRED

    def is_invalid(self) -> bool:
        """Tell whether the token's times do not hold."""
        return self._state == INVALID

    def _check_issued_at(self) -> None:
        """Mark the token invalid when its issued-at lies in the future."""
        issued_at = self._payload.get("iat")
        if not isinstance(issued_at, (int, float)) or isinstance(issued_at, bool):
            return
        now = int(self._clock.now().timestamp())
        if issued_at - self._clock_skew > now:
            self._state = INVALID

    def _check_not_before(self) -> None:
        """Mark the token invalid when its not-before time has not yet been reached."""
        not_before = self._payload.get("nbf")
        if not isinstance(not_before, (int, float)) or isinstance(not_before, bool):
            return
        now = int(self._clock.now().timestamp())
        if not_before - self._clock_skew > now:
            self._state = INVALID

    def _check_expiration(self) -> None:
        """Judge the expiry the token carries; tolerate a missing one when allowed."""
        if self._state == INVALID:
            return
        expires_at = self._payload.get("exp")
        if not isinstance(expires_at, (int, float)) or isinstance(expires_at, bool):
            if not self._allow_no_expiration:
                self._state = INVALID
            return
        now = int(self._clock.now().timestamp())
        if now - self._clock_skew >= expires_at:
            self._state = EXPIRED
