"""The signature algorithms this library signs and verifies with.

``"none"`` is deliberately absent: an unsigned token is never accepted, and the
verifier is only ever built with algorithms from this set, so a token presenting
any other is refused before its signature is even considered.
"""

from __future__ import annotations

from typing import Final

from xtr_security_core.exception import InvalidArgumentError

__all__ = [
    "ALLOWED_ALGORITHMS",
    "HMAC_ALGORITHMS",
    "key_type_for_algorithm",
]

#: Every signature algorithm this library will sign or verify with.
ALLOWED_ALGORITHMS: Final[frozenset[str]] = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
        "HS256",
        "HS384",
        "HS512",
    },
)

#: The shared-secret algorithms, the only ones an asymmetric key set refuses.
HMAC_ALGORITHMS: Final[frozenset[str]] = frozenset({"HS256", "HS384", "HS512"})

_ALGORITHM_KEY_TYPES: Final[dict[str, str]] = {
    "RS256": "RSA",
    "RS384": "RSA",
    "RS512": "RSA",
    "PS256": "RSA",
    "PS384": "RSA",
    "PS512": "RSA",
    "ES256": "EC",
    "ES384": "EC",
    "ES512": "EC",
    "EdDSA": "OKP",
    "HS256": "oct",
    "HS384": "oct",
    "HS512": "oct",
}


def key_type_for_algorithm(algorithm: str) -> str:
    """Return the JWK key type (``kty``) a signature algorithm demands.

    ``RS*``/``PS*`` need an ``RSA`` key, ``ES*`` an ``EC`` key, ``EdDSA`` an
    ``OKP`` key and ``HS*`` an ``oct`` secret.

    Raises:
        InvalidArgumentError: When ``algorithm`` is not one this library signs
            or verifies with.
    """
    try:
        return _ALGORITHM_KEY_TYPES[algorithm]
    except KeyError as error:
        allowed = sorted(ALLOWED_ALGORITHMS)
        raise InvalidArgumentError(
            f"Algorithm {algorithm!r} is not supported; allowed algorithms are {allowed}.",
        ) from error
