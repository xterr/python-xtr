"""Certificates and keys made for the test run: a CA, an intermediate, signers and recipients.

No certificate is committed: each is generated once per run with cryptography and written to
a test's own directory when a signer or an encrypter needs a file to read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import TYPE_CHECKING, Final

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "Identity",
    "authority",
    "broken_key_certificate_pem",
    "chained_signer",
    "ec_signer",
    "intermediate",
    "other_recipient",
    "recipient",
    "rsa_pss_certificate_pem",
    "signer_identity",
    "unsupported_key_certificate_pem",
]

_PrivateKey = rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey
# The DER of the P-256 curve's OID, and of SM2's, which cryptography loads no key of.
_P256: Final = bytes.fromhex("06082a8648ce3d030107")
_SM2: Final = bytes.fromhex("06082a811ccf5501822d")
# rsaEncryption with its NULL parameters, and RSASSA-PSS with its default ones: as long.
_RSA_ENCRYPTION: Final = bytes.fromhex("06092a864886f70d0101010500")
_RSASSA_PSS: Final = bytes.fromhex("06092a864886f70d01010a3000")


@dataclass(frozen=True, slots=True)
class Identity:
    """A certificate and the private key of its public key."""

    certificate: x509.Certificate
    private_key: _PrivateKey

    def certificate_pem(self) -> bytes:
        """Return the certificate as PEM."""
        return self.certificate.public_bytes(serialization.Encoding.PEM)

    def key_pem(self, passphrase: str = "") -> bytes:
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
        )

    def write(self, directory: Path, name: str, passphrase: str = "") -> tuple[Path, Path]:
        """Write ``<name>.crt`` and ``<name>.key`` to ``directory``; return their paths."""
        certificate = directory / f"{name}.crt"
        key = directory / f"{name}.key"
        _ = certificate.write_bytes(self.certificate_pem())
        _ = key.write_bytes(self.key_pem(passphrase))
        return certificate, key


def _rsa() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _issue(name: str, private_key: _PrivateKey, issuer: Identity | None) -> Identity:
    """Issue a certificate for ``name``, a CA's when it ends in CA, self-signed with no issuer."""
    is_authority = name.endswith("CA")
    now = datetime.now(UTC)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    issuer_key = private_key if issuer is None else issuer.private_key
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject if issuer is None else issuer.certificate.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=is_authority, path_length=None), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),
            critical=False,
        )
        .add_extension(_key_usage(is_authority=is_authority), critical=True)
    )
    if not is_authority:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False
        ).add_extension(
            x509.SubjectAlternativeName([x509.RFC822Name(f"{name}@example.com")]), critical=False
        )
    return Identity(builder.sign(issuer_key, hashes.SHA256()), private_key)


def _key_usage(*, is_authority: bool) -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=not is_authority,
        content_commitment=False,
        key_encipherment=not is_authority,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=is_authority,
        crl_sign=is_authority,
        encipher_only=False,
        decipher_only=False,
    )


@cache
def authority() -> Identity:
    """Return the run's root CA, the one a verifier trusts."""
    return _issue("Test Root CA", _rsa(), None)


@cache
def intermediate() -> Identity:
    """Return a CA issued by the root, which issues :func:`chained_signer`."""
    return _issue("Test Intermediate CA", _rsa(), authority())


@cache
def signer_identity() -> Identity:
    """Return a signer issued by the root CA."""
    return _issue("signer", _rsa(), authority())


@cache
def chained_signer() -> Identity:
    """Return a signer issued by the intermediate CA: a verifier needs the intermediate too."""
    return _issue("chained", _rsa(), intermediate())


@cache
def ec_signer() -> Identity:
    """Return a signer with an elliptic-curve key, issued by the root CA."""
    return _issue("elliptic", ec.generate_private_key(ec.SECP256R1()), authority())


@cache
def recipient() -> Identity:
    """Return the first recipient a message is encrypted for."""
    return _issue("fabien", _rsa(), authority())


@cache
def other_recipient() -> Identity:
    """Return a second recipient, with a key of its own."""
    return _issue("luna", _rsa(), authority())


def _rewritten(identity: Identity, old: bytes, new: bytes) -> bytes:
    """Return the certificate of ``identity`` as PEM, the one ``old`` of its DER made ``new``.

    The issuer's signature no longer holds; a certificate's key is read without checking it.
    """
    der = identity.certificate.public_bytes(serialization.Encoding.DER)
    assert der.count(old) == 1
    certificate = x509.load_der_x509_certificate(der.replace(old, new))
    return certificate.public_bytes(serialization.Encoding.PEM)


def unsupported_key_certificate_pem() -> bytes:
    """Return a certificate whose key is on SM2, a curve cryptography does not load."""
    return _rewritten(ec_signer(), _P256, _SM2)


def broken_key_certificate_pem() -> bytes:
    """Return a certificate whose EC key is a point off its curve."""
    der = bytearray(ec_signer().certificate.public_bytes(serialization.Encoding.DER))
    # The point follows the curve's OID: a BIT STRING header, then its coordinates.
    der[der.index(_P256) + len(_P256) + 10] ^= 0xFF
    certificate = x509.load_der_x509_certificate(bytes(der))
    return certificate.public_bytes(serialization.Encoding.PEM)


def rsa_pss_certificate_pem() -> bytes:
    """Return the signer's certificate, its RSA key marked as one for RSASSA-PSS only."""
    return _rewritten(signer_identity(), _RSA_ENCRYPTION, _RSASSA_PSS)
