"""The token hash an ID token carries for a token issued beside it.

An ID token answered together with an access token carries that token's hash
as ``at_hash``. A client that verified the ID token's signature recomputes the
hash over the access token it received: when the two agree, the access token is
the one the server issued with the ID token, not one swapped in on the way. The
hash is the left half of the token's digest under the hash function of the ID
token's signature algorithm, base64url-encoded without padding (OpenID Connect
Core 1.0, Section 3.1.3.6). ``EdDSA`` names no hash function of its own: the
curve of its key does (OpenID Connect Token Hash Algorithm Implementer's Guide
1.0, Section 2).
"""

from __future__ import annotations

import base64
import hashlib
from typing import Final

from xtr_security_openid_connect_server.exception.unsupported_algorithm_error import (
    UnsupportedAlgorithmError,
)

__all__ = ["token_hash"]

#: How many octets of SHAKE256 an Ed448 signature hashes with (RFC 8032,
#: Section 5.2): the digest whose left half binds a token beside one.
_ED448_DIGEST_SIZE: Final = 114


def token_hash(token: str, algorithm: str, curve: str | None = None) -> str:
    """Return the hash of ``token`` an ID token signed with ``algorithm`` carries.

    The digest is the one the algorithm signs with, read off its name as a
    client reads it off the ``alg`` header: a name ending in ``256``, ``384``
    or ``512`` signs with SHA-256, SHA-384 or SHA-512. ``EdDSA`` names none: it
    signs with SHA-512 over Ed25519 and with 114 octets of SHAKE256 over Ed448,
    so the curve of its key decides, as a client reads it off the key it
    verifies the token with — and an ``EdDSA`` token given no curve is hashed
    as Ed25519's. Any other name or curve is refused rather than guessed at.
    Half the digest is kept: enough to bind the token, short enough not to
    swell the ID token.

    Args:
        token: The token as the client receives it. A token is ASCII, and the
            hash is defined over those octets.
        algorithm: The ``alg`` the ID token is signed with.
        curve: The ``crv`` of the key an ``EdDSA`` ID token is signed with,
            ``Ed25519`` or ``Ed448``. No other algorithm reads it.

    Returns:
        The left half of the digest, base64url-encoded without padding.

    Raises:
        UnsupportedAlgorithmError: When ``algorithm`` names none of those
            digests, or ``EdDSA`` is asked for over neither curve.
    """
    octets = token.encode("ascii")
    if algorithm == "EdDSA":
        digest = _edwards_digest(octets, curve)
    elif algorithm.endswith("512"):
        digest = hashlib.sha512(octets).digest()
    elif algorithm.endswith("384"):
        digest = hashlib.sha384(octets).digest()
    elif algorithm.endswith("256"):
        digest = hashlib.sha256(octets).digest()
    else:
        raise UnsupportedAlgorithmError(algorithm)
    return base64.urlsafe_b64encode(digest[: len(digest) // 2]).rstrip(b"=").decode("ascii")


def _edwards_digest(octets: bytes, curve: str | None) -> bytes:
    """Return the digest an ``EdDSA`` signature over ``curve`` hashes ``octets`` with.

    Raises:
        UnsupportedAlgorithmError: When ``curve`` is neither Edwards curve.
    """
    match curve:
        case None | "Ed25519":
            return hashlib.sha512(octets).digest()
        case "Ed448":
            return hashlib.shake_256(octets).digest(_ED448_DIGEST_SIZE)
        case _:
            raise UnsupportedAlgorithmError("EdDSA", curve)
