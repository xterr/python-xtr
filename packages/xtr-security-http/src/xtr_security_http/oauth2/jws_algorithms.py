"""The JWS algorithms an OAuth2 client signs what it sends with, by their JWA name.

Nothing here needs the JOSE library at import time: the algorithms are named
as the library spells them, and what a name constrains — the type of the key,
the curve an ECDSA one signs on — is declared here, so the allow-lists a
client-authentication method builds are plain mappings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from joserfc.jwk import Key

__all__ = ["JwsAlgorithms"]


@final
class JwsAlgorithms:
    """The algorithm names an OAuth2 client signs with, and what each asks of its key.

    The two sets are kept apart because what a key may be follows from the
    algorithm: a shared secret signing where an asymmetric key is expected, or
    the other way round, turns a value both parties hold into a signature one
    of them is supposed to be the only one able to make. The JOSE library
    selects an algorithm by its name, so the names are the mapping's keys and
    the key type each demands is its value — the translation of the algorithm
    classes the upstream suite maps onto the local library.
    """

    __slots__ = ()

    ASYMMETRIC: Final[Mapping[str, str]] = {
        "RS256": "RSA",
        "RS384": "RSA",
        "RS512": "RSA",
        "ES256": "EC",
        "ES384": "EC",
        "ES512": "EC",
        "PS256": "RSA",
        "PS384": "RSA",
        "PS512": "RSA",
    }
    """The asymmetric algorithms, the ones a DPoP proof and a "private_key_jwt"
    assertion are signed with — RFC 9449, Section 4.2 excludes the symmetric
    ones, and so does a key the provider only ever held the public half of."""

    CURVES: Final[Mapping[str, str]] = {
        "ES256": "P-256",
        "ES384": "P-384",
        "ES512": "P-521",
    }
    """The curve each ECDSA algorithm signs on, RFC 7518, Section 3.4.

    The algorithm names both the hash and the curve, and a signature made over
    another curve is of the wrong length for it: the JOSE library only checks
    that an EC key carries a "crv", so this is what tells P-384 from P-256
    before anything is signed."""

    MAC: Final[Mapping[str, str]] = {
        "HS256": "oct",
        "HS384": "oct",
        "HS512": "oct",
    }
    """The MAC algorithms, keyed with a secret both the client and the provider
    hold."""

    @classmethod
    def check_key(cls, key: Key, algorithm: str) -> None:
        """Check that ``key`` can make the signatures ``algorithm`` is named for.

        Read before anything is signed rather than at the first signature: a
        key of the wrong type or on the wrong curve is a misconfiguration, and
        finding it out on the request that needed it turns it into a failure
        on a user who has already logged in elsewhere.

        Args:
            key: The key the assertion would be signed with.
            algorithm: The JWA name of the algorithm it would be signed with,
                one this suite knows — an unknown name is refused the same way,
                since what a key may be cannot be read off it.

        Raises:
            InvalidArgumentError: When the algorithm is not one this suite signs
                with, or the key is of the wrong type for it, or an ECDSA
                algorithm's key is on another curve than the one it signs on.
        """
        key_type = cls.ASYMMETRIC.get(algorithm, cls.MAC.get(algorithm))
        if key_type is None:
            raise InvalidArgumentError(
                f'"{algorithm}" is not a JWS algorithm an OAuth2 client signs with. '
                'Use one of "RS256", "RS384", "RS512", "ES256", "ES384", "ES512", '
                '"PS256", "PS384", "PS512", "HS256", "HS384", "HS512".',
            )
        if key.key_type != key_type:
            raise InvalidArgumentError(
                f'The "{algorithm}" algorithm signs with a key of the "{key_type}" '
                f'type, and the given JWK is of the "{key.key_type}" type.',
            )
        curve = cls.CURVES.get(algorithm)
        if curve is None:
            return
        key_curve = key.get("crv")
        if curve != key_curve:
            raise InvalidArgumentError(
                f'The "{algorithm}" algorithm signs with a key on the "{curve}" curve '
                f'(RFC 7518, Section 3.4), and the given JWK is on the "{key_curve}" curve.',
            )
