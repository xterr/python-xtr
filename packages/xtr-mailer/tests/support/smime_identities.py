"""S/MIME certificates and keys made for the test run: a CA and the people mail goes between.

No certificate is committed: each is generated once per run with cryptography and written to
a test's own directory when a signer, an encrypter or a repository needs a file to read.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, final

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from xtr_clock import SystemClock

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["Identity", "authority", "identity"]


@final
@dataclass(frozen=True, slots=True)
class Identity:
    """A certificate and the RSA private key of its public key."""

    certificate: x509.Certificate
    private_key: rsa.RSAPrivateKey

    def write(self, directory: Path, name: str, passphrase: str = "") -> tuple[Path, Path]:
        """Write ``<name>.crt`` and ``<name>.key`` to ``directory``; return their paths.

        The key is encrypted with ``passphrase`` when one is given.
        """
        encryption = (
            serialization.BestAvailableEncryption(passphrase.encode())
            if passphrase
            else serialization.NoEncryption()
        )
        certificate, key = directory / f"{name}.crt", directory / f"{name}.key"
        _ = certificate.write_bytes(self.certificate.public_bytes(serialization.Encoding.PEM))
        _ = key.write_bytes(
            self.private_key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, encryption
            )
        )
        return certificate, key


def _issue(address: str | None, issuer: Identity | None) -> Identity:
    """Issue a certificate for ``address``; with neither, the self-signed CA's."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, address or "Test Root CA")])
    issuer_key = key if issuer is None else issuer.private_key
    # cryptography needs a plain datetime: it cannot strip the zone of the clock's subclass.
    now = datetime.datetime.fromtimestamp(SystemClock("UTC").now().timestamp(), datetime.UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name if issuer is None else issuer.certificate.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=issuer is None, path_length=None), critical=True)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),
            critical=False,
        )
    )
    if address is not None:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False
        ).add_extension(x509.SubjectAlternativeName([x509.RFC822Name(address)]), critical=False)
    return Identity(builder.sign(issuer_key, hashes.SHA256()), key)


@cache
def authority() -> Identity:
    """Return the run's root CA, the one a verifier trusts."""
    return _issue(None, None)


@cache
def identity(address: str) -> Identity:
    """Return the run's certificate for ``address``, issued by the root CA."""
    return _issue(address, authority())
