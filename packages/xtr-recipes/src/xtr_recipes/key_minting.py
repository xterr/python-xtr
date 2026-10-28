"""Minting the private key a ``[keys]`` entry asks for, as a PEM."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes

__all__ = ["RSA_KEY_SIZE", "mint_private_key"]

RSA_KEY_SIZE: Final = 2048
"""The modulus of a minted RSA key, in bits: the shortest still considered sound."""

#: The curve each elliptic-curve algorithm is defined over: the algorithm names
#: the hash and the curve together, so neither is a choice.
_CURVES: Final[dict[str, ec.EllipticCurve]] = {
    "ES256": ec.SECP256R1(),
    "ES384": ec.SECP384R1(),
    "ES512": ec.SECP521R1(),
}

#: The public exponent every RSA key is minted with.
_RSA_EXPONENT: Final = 65537


def mint_private_key(algorithm: str, passphrase: str | None) -> str:
    """Return a new private key for ``algorithm`` as PKCS#8 PEM text.

    Args:
        algorithm: One of
            :data:`~xtr_recipes.key_pair_config.KEY_ALGORITHMS`, which the
            manifest has already checked.
        passphrase: What the key is encrypted with, or ``None`` or empty for
            an unencrypted key.

    Returns:
        The PEM, encrypted with the best scheme the library offers when a
        pass phrase is given.
    """
    encryption: serialization.KeySerializationEncryption = (
        serialization.BestAvailableEncryption(passphrase.encode("utf-8"))
        if passphrase
        else serialization.NoEncryption()
    )
    pem = _generate(algorithm).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        encryption,
    )
    return pem.decode("ascii")


def _generate(algorithm: str) -> PrivateKeyTypes:
    """Return a fresh private key of the type and size ``algorithm`` signs with."""
    if algorithm in _CURVES:
        return ec.generate_private_key(_CURVES[algorithm])
    if algorithm == "EdDSA":
        return ed25519.Ed25519PrivateKey.generate()
    return rsa.generate_private_key(public_exponent=_RSA_EXPONENT, key_size=RSA_KEY_SIZE)
