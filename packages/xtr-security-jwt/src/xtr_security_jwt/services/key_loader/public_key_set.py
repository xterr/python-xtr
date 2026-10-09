"""The JWK set a deployment publishes, and the id its signing key is named by."""

from __future__ import annotations

from typing import TYPE_CHECKING

from joserfc.jwk import KeySet
from xtr_security_core.exception import InvalidArgumentError

# The keys are read with the very importers the JWS provider verifies with, so the
# published set holds exactly the keys that will accept a token: a publisher reading
# the material its own way could announce a key the verifier never tries, or hide
# one it does.
from xtr_security_jwt.services.jws_provider._key_material import (
    import_additional_keys,
    import_key,
)

from ._algorithms import HMAC_ALGORITHMS
from .key_loader_interface import TYPE_PUBLIC

if TYPE_CHECKING:
    from joserfc.jwk import Key, KeySetSerialization

    from .key_loader_interface import KeyLoaderInterface

__all__ = ["public_key_set", "signing_key_id"]


def public_key_set(key_loader: KeyLoaderInterface, algorithm: str) -> KeySetSerialization:
    """Return the JWK set a verifier of ``key_loader``'s tokens may be handed.

    The set holds the signing key's public half first, then every additional
    public key the deployment trusts, so a verifier reading it accepts both the
    tokens being signed now and the ones signed by the keys still trusted
    through a rotation. Each key is named as :func:`signing_key_id` names the
    signing one — the ``kid`` its material carries, else its RFC 7638
    thumbprint — and carries its public members alone.

    A verifier built on this library knows each key by that published name as
    well as by the id its own source gave it — the loader's id, an extra's file
    name — so a token whose ``kid`` carries either one finds the key in a single
    lookup.

    The key material is read on every call, so a deployment serving this at an
    endpoint caches the document rather than asking for it per request.

    Args:
        key_loader: Where the signing key and the trusted public keys are read from.
        algorithm: The signature algorithm the keys are for; it decides the key
            type every one of them is read as.

    Returns:
        ``{"keys": [...]}``, ready to be serialised as the published document.

    Raises:
        InvalidArgumentError: When ``algorithm`` signs with a shared secret, when
            the signing key is absent or unreadable, or when a trusted public key
            cannot be read as a key of the algorithm's type.
    """
    keys: list[Key] = [_signing_public_key(key_loader, algorithm)]
    passphrase = key_loader.get_passphrase()
    for extra in key_loader.get_additional_public_keys():
        keys.extend(import_additional_keys(extra, algorithm, passphrase))
    return KeySet(keys).as_dict(private=False)


def signing_key_id(key_loader: KeyLoaderInterface, algorithm: str) -> str:
    """Return the id the signing key is published under, for a token's ``kid``.

    Material that carries a ``kid`` names itself; material that does not — a
    lone PEM — is named by its RFC 7638 thumbprint, which is derived from the
    key's own public members. A signer stamping this into a token header and a
    verifier reading :func:`public_key_set` therefore agree on the id with
    nothing passed between them, and the thumbprint is the same whichever half
    of the pair it is taken from.

    Args:
        key_loader: Where the signing key is read from.
        algorithm: The signature algorithm the key is for.

    Returns:
        The ``kid`` naming the signing key in the published set.

    Raises:
        InvalidArgumentError: When ``algorithm`` signs with a shared secret, or
            the signing key is absent or unreadable.
    """
    key = _signing_public_key(key_loader, algorithm)
    return key.kid or key.thumbprint()


def _signing_public_key(key_loader: KeyLoaderInterface, algorithm: str) -> Key:
    """Import the public half of the key ``algorithm`` signs with.

    A shared secret is refused outright rather than left out of the set: an
    empty — or secret-bearing — document would either tell a verifier there is
    no key while tokens are being signed, or hand it the key that signs them.
    Naming the algorithm says which of the two a deployment configured.

    Raises:
        InvalidArgumentError: When ``algorithm`` signs with a shared secret, or
            the public half is absent or cannot be read as a key of its type.
    """
    if algorithm in HMAC_ALGORITHMS:
        raise InvalidArgumentError(
            f"{algorithm} signs with a shared secret, which has no public half to publish: "
            "a key set is only ever built for an asymmetric signing key.",
        )
    return import_key(key_loader.load_key(TYPE_PUBLIC), algorithm, key_loader.get_passphrase())
