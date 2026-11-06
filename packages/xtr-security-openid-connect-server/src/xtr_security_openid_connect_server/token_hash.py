"""The token hash an ID token carries for a token issued beside it.

An ID token answered together with an access token carries that token's hash
as ``at_hash``. A client that verified the ID token's signature recomputes the
hash over the access token it received: when the two agree, the access token is
the one the server issued with the ID token, not one swapped in on the way. The
hash is the left half of the token's digest under the hash function of the ID
token's signature algorithm, base64url-encoded without padding (OpenID Connect
Core 1.0, Section 3.1.3.6).
"""

from __future__ import annotations

import base64
import hashlib

from xtr_security_openid_connect_server.exception.unsupported_algorithm_error import (
    UnsupportedAlgorithmError,
)

__all__ = ["token_hash"]


def token_hash(token: str, algorithm: str) -> str:
    """Return the hash of ``token`` an ID token signed with ``algorithm`` carries.

    The digest is the one the algorithm signs with, read off its name as a
    client reads it off the ``alg`` header: a name ending in ``256``, ``384``
    or ``512`` signs with SHA-256, SHA-384 or SHA-512. ``EdDSA`` names no size
    and is hashed with SHA-512, the digest Ed25519 signs with; any other name
    is refused rather than guessed at. Half the digest is kept: enough to bind
    the token, short enough not to swell the ID token.

    Args:
        token: The token as the client receives it. A token is ASCII, and the
            hash is defined over those octets.
        algorithm: The ``alg`` the ID token is signed with.

    Returns:
        The left half of the digest, base64url-encoded without padding.

    Raises:
        UnsupportedAlgorithmError: When ``algorithm`` names none of those
            digests.
    """
    if algorithm == "EdDSA" or algorithm.endswith("512"):
        digest_name = "sha512"
    elif algorithm.endswith("384"):
        digest_name = "sha384"
    elif algorithm.endswith("256"):
        digest_name = "sha256"
    else:
        raise UnsupportedAlgorithmError(algorithm)
    digest = hashlib.new(digest_name, token.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest[: len(digest) // 2]).rstrip(b"=").decode("ascii")
