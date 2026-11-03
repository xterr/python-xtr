"""A DKIM signing key for ``example.com``, and the DNS answer publishing its public half."""

from __future__ import annotations

import base64
from functools import cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

__all__ = ["SELECTOR", "private_key_pem", "published_key"]

SELECTOR = "default"


@cache
def _key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def private_key_pem() -> str:
    """Return the private key as PEM text, as a signer takes it."""
    return (
        _key()
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode("ascii")
    )


def published_key(name: bytes, timeout: int = 5) -> bytes | None:
    """Answer the TXT query for ``default._domainkey.example.com.``, as DNS would."""
    del timeout
    if name != f"{SELECTOR}._domainkey.example.com.".encode("ascii"):
        return None
    public = (
        _key()
        .public_key()
        .public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    return b"v=DKIM1; k=rsa; p=" + base64.b64encode(public)
