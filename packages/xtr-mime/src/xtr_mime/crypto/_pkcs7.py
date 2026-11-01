"""The one module importing the smime extra: cryptography signs and encrypts with PKCS #7.

It reads the certificates and keys too. Importing it without the extra raises
``ImportError``; :class:`~xtr_mime.crypto.SMimeSigner` and
:class:`~xtr_mime.crypto.SMimeEncrypter` turn that into an error naming the extra.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import PublicKeyAlgorithmOID

from xtr_mime._error_text import escaped
from xtr_mime.exception import InvalidArgumentError

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.types import CertificatePublicKeyTypes

    from ._s_mime import PemFile

__all__ = ["Envelope", "Signature", "load_certificates", "load_key_pair", "load_recipient"]

_HASHES: Final = {
    "sha224": hashes.SHA224,
    "sha256": hashes.SHA256,
    "sha384": hashes.SHA384,
    "sha512": hashes.SHA512,
}
_CIPHERS: Final = {"aes-128-cbc": algorithms.AES128, "aes-256-cbc": algorithms.AES256}
# A line end that is not CRLF: a bare CR, or a bare LF.
_BARE_LINE_END: Final = re.compile(rb"\r(?!\n)|(?<!\r)\n")
# A verifier refuses a signature made with a shorter RSA key, as cryptography refuses to make
# one with some digests.
_MIN_KEY_SIZE: Final = 1024

_SigningPrivateKey = rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey


@final
@dataclass(frozen=True, slots=True, repr=False)
class Signature:
    """What a detached signature is made with; shown as nothing, it holds a private key."""

    certificate: x509.Certificate
    private_key: _SigningPrivateKey
    extra_certificates: tuple[x509.Certificate, ...]
    algorithm: str
    """One of ``sha224``, ``sha256``, ``sha384``, ``sha512``, checked before."""

    def sign(self, data: bytes) -> bytes:
        """Return ``data`` signed: a ``multipart/signed`` message holding it and the signature.

        ``data`` is signed in the canonical form S/MIME signs, every line ending in CRLF — the
        form the message holds it in. A bare CR, which a forwarded message may hold, is made a
        CRLF here: cryptography writes it so but would sign it as it is.
        """
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(_BARE_LINE_END.sub(b"\r\n", data))
            .add_signer(self.certificate, self.private_key, _HASHES[self.algorithm]())
        )
        for certificate in self.extra_certificates:
            builder = builder.add_certificate(certificate)
        return builder.sign(serialization.Encoding.SMIME, [pkcs7.PKCS7Options.DetachedSignature])


@final
@dataclass(frozen=True, slots=True)
class Envelope:
    """Who a message is encrypted for, and with which cipher."""

    recipients: tuple[x509.Certificate, ...]
    """At least one, each with an RSA key, checked before."""
    cipher: str
    """``aes-128-cbc`` or ``aes-256-cbc``, checked before."""

    def encrypt(self, data: bytes) -> bytes:
        """Return ``data`` encrypted: an ``application/pkcs7-mime`` enveloped-data message.

        ``data`` is encrypted in its canonical form, every line ending in CRLF.
        """
        builder = pkcs7.PKCS7EnvelopeBuilder().set_data(data)
        for certificate in self.recipients:
            builder = builder.add_recipient(certificate)
        builder = builder.set_content_encryption_algorithm(_CIPHERS[self.cipher])
        return builder.encrypt(serialization.Encoding.SMIME, [])


def load_certificates(file: PemFile) -> list[x509.Certificate]:
    """Read every certificate of ``file``, in order.

    Raises:
        InvalidArgumentError: The file holds no PEM certificate, or one that does not load.
    """
    try:
        return x509.load_pem_x509_certificates(file.content)
    except ValueError as error:
        raise InvalidArgumentError(
            f'Unable to load S/MIME certificate "{escaped(file.path)}": {escaped(str(error))}'
        ) from error


def load_recipient(file: PemFile) -> x509.Certificate:
    """Read the certificate a message is encrypted for: the first of ``file``.

    Raises:
        InvalidArgumentError: The certificate or its key does not load, or its key is not RSA,
            the one kind cryptography encrypts for.
    """
    certificate = load_certificates(file)[0]
    if not isinstance(_public_key(certificate, file), rsa.RSAPublicKey):
        raise InvalidArgumentError(
            f'The S/MIME certificate "{escaped(file.path)}" holds a key that is not RSA: a '
            "message is encrypted only for an RSA key."
        )
    return certificate


def load_key_pair(
    certificate: PemFile, private_key: PemFile, passphrase: str
) -> tuple[x509.Certificate, _SigningPrivateKey]:
    """Read the signing certificate — the first of its file — and the private key of its key.

    Raises:
        InvalidArgumentError: The certificate, its key or the private key does not load, the
            certificate's key is for RSA-PSS, the private key is neither RSA of at least 1024
            bits nor EC, or it is not the key of the certificate.
    """
    signer = load_certificates(certificate)[0]
    public_key = _public_key(signer, certificate)
    if signer.public_key_algorithm_oid == PublicKeyAlgorithmOID.RSASSA_PSS:
        # cryptography signs with PKCS #1 v1.5 padding, which a verifier refuses for such a key.
        raise InvalidArgumentError(
            f'The S/MIME certificate "{escaped(certificate.path)}" holds an RSA-PSS key: a '
            "message is signed only with an RSA key for PKCS #1 v1.5 signatures, or an EC key."
        )
    key = _load_private_key(private_key, passphrase)
    if public_key != key.public_key():
        raise InvalidArgumentError(
            f'The S/MIME private key "{escaped(private_key.path)}" does not match the certificate '
            f'"{escaped(certificate.path)}".'
        )
    return signer, key


def _public_key(certificate: x509.Certificate, file: PemFile) -> CertificatePublicKeyTypes:
    """Read the key of ``certificate``, which cryptography reads only when asked for it.

    Raises:
        InvalidArgumentError: The key is of a kind cryptography does not load, or its bytes are
            not a key; the error names the problem, never the key.
    """
    try:
        return certificate.public_key()
    except (ValueError, UnsupportedAlgorithm) as error:
        raise InvalidArgumentError(
            f'Unable to load the key of S/MIME certificate "{escaped(file.path)}": '
            f"{escaped(str(error))}"
        ) from error


def _load_private_key(file: PemFile, passphrase: str) -> _SigningPrivateKey:
    """Open the key of ``file``, decrypting it with ``passphrase`` when it is not empty.

    The passphrase is encoded as the file system encodes a name: one read from the command
    line or the environment with bytes that are not UTF-8 holds them as surrogates, and opens
    the key with those bytes. cryptography's own reason for refusing a key names the problem,
    never the key; the passphrase is in no error of the chain.

    Raises:
        InvalidArgumentError: The key does not open — not PEM, encrypted and the passphrase
            missing, wrong or not text at all, a passphrase given for a key that is not
            encrypted — or it is neither RSA of at least 1024 bits nor EC.
    """
    prefix = f'Unable to load S/MIME private key "{escaped(file.path)}": '
    try:
        secret: bytes | None = passphrase.encode("utf-8", "surrogateescape") or None
        encodable = True
    except UnicodeEncodeError:
        # Raised outside this block: the codec's error holds the whole passphrase, and an
        # error raised here would carry it as its context.
        secret, encodable = None, False
    if not encodable:
        raise InvalidArgumentError(f"{prefix}the passphrase is not text that can be encoded.")
    try:
        key = serialization.load_pem_private_key(file.content, secret)
    except (TypeError, ValueError, UnsupportedAlgorithm) as error:
        raise InvalidArgumentError(f"{prefix}{escaped(str(error))}") from error
    if not isinstance(key, (rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey)):
        raise InvalidArgumentError(f"{prefix}only an RSA or EC key signs S/MIME.")
    if isinstance(key, rsa.RSAPrivateKey) and key.key_size < _MIN_KEY_SIZE:
        raise InvalidArgumentError(
            f"{prefix}the RSA key has {key.key_size} bits; S/MIME needs at least {_MIN_KEY_SIZE}."
        )
    return key
