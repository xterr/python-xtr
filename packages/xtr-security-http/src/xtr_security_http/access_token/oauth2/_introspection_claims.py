"""Reading and confronting the members of a token introspection response.

RFC 7662 Section 2.2 makes every member of the response optional and leaves
the checks on the authorization server, so nothing here is refused for being
absent: a member is confronted only when the response carries it, and the
issuer and the audience only when this resource server declared which ones it
expects — a token issued by another authorization server, or for another
resource server, must not be honored.
"""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING, Final, cast

from xtr_security_http.exception.invalid_access_token_error import InvalidAccessTokenError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "matches_audience",
    "numeric_seconds",
    "read_timestamp",
    "user_identifier",
    "verify_members",
]

_INT_MAX: Final = 2**63
"""The magnitude a reported timestamp may not reach.

Beyond it the number describes no instant a clock confronts — the bound the
upstream handler holds so a member carrying an absurd magnitude cannot pose as
a date.
"""


def numeric_seconds(value: object) -> float | None:
    """Read ``value`` as a number of seconds, or ``None`` when it is not one.

    A JSON null reads as no value, which RFC 7662 Section 2.2 allows a member
    to carry; anything else that is not a number — a boolean included, which
    Python counts among the numbers — is no timestamp either.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str):
        try:
            seconds = float(value)
        except ValueError:
            return None
    else:
        return None
    return seconds if isfinite(seconds) else None


def read_timestamp(claims: Mapping[str, object], claim: str) -> int | None:
    """Read a date member of the introspection response, or ``None`` when absent.

    RFC 7662 Section 2.2 types ``exp``, ``nbf`` and ``iat`` as integer
    timestamps, so a member carrying anything else describes no instant this
    resource server can confront its clock with, and the response is refused
    rather than honored. A JSON null is read as an absent member, which that
    section allows.

    Raises:
        InvalidAccessTokenError: When the member holds anything but a number
            a clock can read.
    """
    value = claims.get(claim)
    if value is None:
        return None
    seconds = numeric_seconds(value)
    if seconds is None or abs(seconds) >= _INT_MAX:
        raise InvalidAccessTokenError(
            f'The "{claim}" claim reported by the authorization server is not a timestamp.',
        )
    return int(seconds)


def matches_audience(audience: object, audiences: tuple[str, ...]) -> bool:
    """Tell whether ``audience`` names one of ``audiences``.

    RFC 7662 Section 2.2 makes ``aud`` "a service-specific string identifier or
    list of string identifiers", so both shapes are read and a single match is
    enough: an access token minted for several resource servers is meant for
    each of them.
    """
    values: Sequence[object] = (
        cast("Sequence[object]", audience) if isinstance(audience, (list, tuple)) else [audience]
    )
    named = {one for one in values if isinstance(one, str)}
    return bool(named.intersection(audiences))


def user_identifier(claims: Mapping[str, object], claim: str | None) -> str:
    """Read the user identifier out of the introspection response.

    A configured ``claim`` is the only one read; without one the ``sub`` is
    read and the ``username`` falls back, the two members RFC 7662 Section 2.2
    names for the resource owner.

    Raises:
        InvalidAccessTokenError: When the configured claim, or both ``sub``
            and ``username``, are missing or hold nothing usable.
    """
    if claim is not None:
        identifier = _read_identifier(claims, claim)
        if identifier is None:
            raise InvalidAccessTokenError(
                f'"{claim}" claim not found on the authorization server response.',
            )
        return identifier
    identifier = _read_identifier(claims, "sub")
    if identifier is None:
        identifier = _read_identifier(claims, "username")
    if identifier is None:
        raise InvalidAccessTokenError(
            '"sub" and "username" claims not found on the authorization server '
            "response. At least one is required.",
        )
    return identifier


def _read_identifier(claims: Mapping[str, object], claim: str) -> str | None:
    """Read ``claim`` as a non-empty identifier, or ``None`` when it holds none."""
    value = claims.get(claim)
    if isinstance(value, str) and value:
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def verify_members(  # noqa: PLR0913 -- the confrontation needs the expectations and the clock
    claims: Mapping[str, object],
    *,
    signed: bool,
    issuer: str | None,
    audiences: tuple[str, ...],
    drift: int,
    now: int,
) -> None:
    """Confront the members of the introspection response with what this resource server expects.

    The dates are only verified when the response carries them: a resource
    server told the token is already expired, not valid yet or minted in the
    future still has no reason to honor it. The issuer and the audience are
    checked when this resource server declares which ones it expects, and the
    response is then required to carry them. A signed response is the
    exception: RFC 9701 Section 5 already binds it to both at the top level of
    the JWT, so the members it wraps are only confronted with them when they
    repeat them.

    Raises:
        InvalidAccessTokenError: When a member the response carries contradicts
            what this resource server expects of it.
    """
    exp = read_timestamp(claims, "exp")
    if exp is not None and exp <= now - drift:
        raise InvalidAccessTokenError(
            "The token reported by the authorization server has expired.",
        )
    nbf = read_timestamp(claims, "nbf")
    if nbf is not None and nbf > now + drift:
        raise InvalidAccessTokenError(
            "The token reported by the authorization server is not valid yet.",
        )
    iat = read_timestamp(claims, "iat")
    if iat is not None and iat > now + drift:
        raise InvalidAccessTokenError(
            "The token reported by the authorization server was issued in the future.",
        )
    if issuer is not None and (not signed or "iss" in claims) and claims.get("iss") != issuer:
        reported = claims.get("iss")
        raise InvalidAccessTokenError(
            'The token was issued by "'
            f'{reported if isinstance(reported, str) else ""}", where "{issuer}" was expected.',
        )
    if (
        audiences
        and (not signed or "aud" in claims)
        and not matches_audience(
            claims.get("aud"),
            audiences,
        )
    ):
        joined = '", "'.join(audiences)
        raise InvalidAccessTokenError(
            f'The token is not intended for any of the audiences "{joined}".',
        )
