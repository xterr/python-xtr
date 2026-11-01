"""RSA keys made for the test run, and the DNS answer a DKIM verifier reads the public half from.

No key is committed: each is generated once per run. :meth:`DkimKey.resolve` stands in for
DNS, so :meth:`DkimKey.verifies` checks a signature with dkimpy's own verifier and no network.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import cache
from typing import Final

import dkim
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from tests.support import short_rsa_key

__all__ = [
    "DOMAIN",
    "SELECTOR",
    "DkimKey",
    "dkim_key",
    "ed25519_pem",
    "other_dkim_key",
    "short_rsa_pem",
]

DOMAIN: Final = "testdkim.example.net"
SELECTOR: Final = "sf"


@dataclass(frozen=True, slots=True)
class DkimKey:
    """An RSA key pair: the private half as PEM, the public half published for every selector."""

    private_key: rsa.RSAPrivateKey

    def pem(self, passphrase: str = "") -> str:
        """Return the private key as PKCS#8 PEM, encrypted with ``passphrase`` when one is given.

        The passphrase is encoded as the file system encodes a name, so one read from the
        command line with bytes that are not UTF-8 encrypts with those bytes.
        """
        encryption = (
            serialization.BestAvailableEncryption(passphrase.encode("utf-8", "surrogateescape"))
            if passphrase
            else serialization.NoEncryption()
        )
        return self.private_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, encryption
        ).decode("ascii")

    def traditional_pem(self) -> str:
        """Return the private key as PKCS#1 PEM (``BEGIN RSA PRIVATE KEY``)."""
        return self.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ).decode("ascii")

    def resolve(self, name: bytes, timeout: int = 5) -> bytes | None:
        """Answer the TXT query for any selector of ``testdkim.example.net.``; nothing else."""
        del timeout
        if not name.endswith(f"._domainkey.{DOMAIN}.".encode("ascii")):
            return None
        public = self.private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return b"v=DKIM1; k=rsa; p=" + base64.b64encode(public)

    def verifies(self, message: bytes) -> bool:
        """Tell whether the first DKIM-Signature of ``message`` verifies against this key."""
        return dkim.verify(message, dnsfunc=self.resolve)


@cache
def dkim_key() -> DkimKey:
    """Return the run's signing key."""
    return DkimKey(rsa.generate_private_key(public_exponent=65537, key_size=2048))


@cache
def other_dkim_key() -> DkimKey:
    """Return a second key, published under the same selector by a :class:`DkimKey` of its own."""
    return DkimKey(rsa.generate_private_key(public_exponent=65537, key_size=2048))


def ed25519_pem() -> str:
    """Return a private key that is not RSA, as PKCS#8 PEM."""
    return (
        ed25519.Ed25519PrivateKey.generate()
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode("ascii")
    )


def short_rsa_pem() -> str:
    """Return a 512-bit RSA key as PKCS#8 PEM: too short for DKIM."""
    return short_rsa_key.short_rsa_pem().decode("ascii")
