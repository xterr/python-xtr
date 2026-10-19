"""Verifying a signed introspection response, as RFC 9701 defines it.

Beyond the signature, two things are checked because RFC 9701 Section 8.1
rests on them to keep an access token or an ID token of the same issuer from
being passed off as an introspection response: the ``typ`` header, and the
nesting of the RFC 7662 members inside the ``token_introspection`` claim. The
``iss``, ``aud`` and ``iat`` claims that Section 5 makes mandatory at the top
level are required as well, and confronted with the issuer and the audiences
this resource server declared.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

from xtr_security_http.exception.invalid_access_token_error import InvalidAccessTokenError

from ._introspection_claims import matches_audience, read_timestamp

if TYPE_CHECKING:
    from joserfc.jwk import KeySet

__all__ = ["verify_signed_response"]

_JWT_RESPONSE_TYPES: Final = frozenset(
    {"token-introspection+jwt", "application/token-introspection+jwt"},
)
"""The ``typ`` header values a signed introspection response carries.

RFC 9701 Section 5 fixes the media type ``application/token-introspection+jwt``
and lets RFC 7515 Section 4.1.9 omit the ``application/`` prefix, so both
spellings are read.
"""

_MANDATORY_CLAIMS: Final = ("iss", "aud", "iat", "token_introspection")
"""The top-level claims RFC 9701 Section 5 makes mandatory."""


def verify_signed_response(  # noqa: PLR0913 -- the RFC 9701 verification needs the key material, the expectations and the clock
    content: bytes,
    *,
    keyset: KeySet,
    algorithms: tuple[str, ...],
    issuer: str | None,
    audiences: tuple[str, ...],
    drift: int,
    now: int,
) -> dict[str, object]:
    """Verify a JWT introspection response and return the members it wraps.

    The signature is verified against ``keyset`` under ``algorithms`` — the
    JOSE library refuses an ``alg`` the allow-list does not name — before
    anything else is read, so a response that fails it is refused whatever
    else it carries.

    Raises:
        InvalidAccessTokenError: When the response is not a verifiable JWT, its
            signature does not verify, its ``typ`` header is not the
            introspection one, a mandatory claim is missing, or a claim
            contradicts what this resource server expects of it.
    """
    from joserfc import jwt  # noqa: PLC0415 -- guarded behind the oidc extra
    from joserfc.errors import (  # noqa: PLC0415 -- guarded behind the oidc extra
        BadSignatureError,
        InvalidKeyIdError,
        JoseError,
        UnsupportedAlgorithmError,
    )

    try:
        token = jwt.decode(content, keyset, algorithms=list(algorithms))
    except (BadSignatureError, InvalidKeyIdError) as error:
        raise InvalidAccessTokenError(
            "The signature of the introspection response is invalid.",
        ) from error
    except UnsupportedAlgorithmError as error:
        raise InvalidAccessTokenError(
            "The algorithm of the introspection response is not one of the allowed ones.",
        ) from error
    except (JoseError, ValueError) as error:
        raise InvalidAccessTokenError(
            "The introspection response is not a valid JWT.",
        ) from error

    typ = token.header.get("typ")
    if not isinstance(typ, str) or typ.lower() not in _JWT_RESPONSE_TYPES:
        raise InvalidAccessTokenError(
            'The "typ" header of the introspection response is not "token-introspection+jwt".',
        )

    payload = token.claims
    if not isinstance(payload, dict):  # pyright: ignore[reportUnnecessaryIsInstance] -- the library types the payload as an object; a response whose payload is not a JSON object decodes to one
        raise InvalidAccessTokenError(
            "The payload of the introspection response is not a JSON object.",
        )
    missing = [claim for claim in _MANDATORY_CLAIMS if payload.get(claim) is None]
    if missing:
        absent = ", ".join(f'"{claim}"' for claim in missing)
        raise InvalidAccessTokenError(
            f"The introspection response is missing the {absent} claim(s).",
        )
    _verify_top_level(payload, issuer=issuer, audiences=audiences, drift=drift, now=now)
    members = payload.get("token_introspection")
    if not isinstance(members, dict):
        raise InvalidAccessTokenError(
            'The "token_introspection" claim of the introspection response is not a JSON object.',
        )
    return dict(cast("dict[str, object]", members))


def _verify_top_level(
    payload: dict[str, object],
    *,
    issuer: str | None,
    audiences: tuple[str, ...],
    drift: int,
    now: int,
) -> None:
    """Confront the mandatory top-level claims with what this resource server expects.

    Raises:
        InvalidAccessTokenError: When the ``iat`` lies in the future, or the
            ``iss`` or ``aud`` contradicts the ones this resource server
            declared.
    """
    iat = read_timestamp(payload, "iat")
    if iat is not None and iat > now + drift:
        raise InvalidAccessTokenError(
            "The introspection response was issued in the future.",
        )
    if issuer is not None and payload.get("iss") != issuer:
        reported = payload.get("iss")
        raise InvalidAccessTokenError(
            'The introspection response was issued by "'
            f'{reported if isinstance(reported, str) else ""}", where "{issuer}" was expected.',
        )
    if audiences and not matches_audience(payload.get("aud"), audiences):
        joined = '", "'.join(audiences)
        raise InvalidAccessTokenError(
            f'The introspection response is not intended for any of the audiences "{joined}".',
        )
