"""Mints the private key a signature algorithm signs with."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from joserfc.jwk import ECKey, OKPKey, RSAKey
from xtr_security_core.exception import InvalidArgumentError

from ._algorithms import key_type_for_algorithm

if TYPE_CHECKING:
    from joserfc.jwk import KeyParameters

__all__ = ["RSA_KEY_SIZE", "generate_signing_key"]

#: The modulus a minted RSA key is given, in bits: the shortest length still
#: considered sound, and the one every ``RS*`` and ``PS*`` algorithm allows.
RSA_KEY_SIZE: Final[int] = 2048

#: The curve each elliptic-curve algorithm is defined over (RFC 7518, Section 3.4):
#: the algorithm names the hash and the curve together, so neither is a choice.
_EC_CURVES: Final[dict[str, str]] = {"ES256": "P-256", "ES384": "P-384", "ES512": "P-521"}


def generate_signing_key(algorithm: str, key_id: str | None = None) -> RSAKey | ECKey | OKPKey:
    """Mint a private key ``algorithm`` signs with, carrying ``key_id`` when given.

    The key holds both halves: its private members sign, and its public ones are
    what a verifier is handed — as a PEM, or in the set
    :func:`~xtr_security_jwt.services.key_loader.public_key_set.public_key_set`
    publishes. A key given no id carries none, and is then named by its RFC 7638
    thumbprint wherever it is published, so a signer and a verifier agree on the
    id without either being told it.

    Args:
        algorithm: The signature algorithm the key is for, one of
            :data:`~xtr_security_jwt.services.key_loader._algorithms.ALLOWED_ALGORITHMS`
            bar the shared-secret ones.
        key_id: The ``kid`` the key material itself carries, or ``None`` for none.

    Returns:
        A private key of the type and size the algorithm demands.

    Raises:
        InvalidArgumentError: When ``algorithm`` is not one this library signs
            with, or signs with a shared secret, which is configured rather than
            minted.
    """
    parameters: KeyParameters = {}
    if key_id is not None:
        parameters["kid"] = key_id
    match key_type_for_algorithm(algorithm):
        case "RSA":
            return RSAKey.generate_key(RSA_KEY_SIZE, parameters=parameters)
        case "EC":
            return ECKey.generate_key(_EC_CURVES[algorithm], parameters=parameters)
        case "OKP":
            return OKPKey.generate_key("Ed25519", parameters=parameters)
        case _:
            raise InvalidArgumentError(
                f"{algorithm} signs with a shared secret, which a deployment configures rather "
                "than mints; a key pair is minted for an RSA, an elliptic-curve or an Edwards "
                "algorithm.",
            )
