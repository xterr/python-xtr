"""A self-signed server certificate, made for the test run that needs it."""

from __future__ import annotations

import datetime
import ipaddress
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import final

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

__all__ = ["Certificate", "make_certificate"]


@final
@dataclass(frozen=True, slots=True)
class Certificate:
    """A certificate and its key on disk, as an ssl context loads them."""

    cert_path: Path
    key_path: Path
    der: bytes

    def server_context(self) -> ssl.SSLContext:
        """Return the context a TLS server presents this certificate with."""
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(self.cert_path, self.key_path)
        return context


def make_certificate(directory: Path) -> Certificate:
    """Write a certificate for ``localhost`` and ``127.0.0.1`` signed by its own key."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = directory / "server.crt"
    key_path = directory / "server.key"
    _ = cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    _ = key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return Certificate(cert_path, key_path, certificate.public_bytes(serialization.Encoding.DER))
