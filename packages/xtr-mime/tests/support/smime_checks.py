"""Check what an S/MIME signer or encrypter sent, with cryptography and nothing of xtr-mime's.

cryptography signs PKCS #7 but has no public verifier, so a signature is checked here by hand:
the signed part is cut from the bytes sent exactly as a mail client receives them, the
signature's SignerInfo is read with a small DER reader, its signed attributes are verified
with the signer certificate's public key, their message digest is compared with the digest of
the signed part, and the signer certificate is followed up to a trusted CA through the
certificates the signature carries. :func:`openssl_verifies` asks ``openssl smime -verify`` the
same question where an ``openssl`` binary is installed.

An encrypted message is decrypted with cryptography's own S/MIME reader.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from typing import TYPE_CHECKING, Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs7

if TYPE_CHECKING:
    from pathlib import Path

    from cryptography import x509

    from tests.support.smime_certificates import Identity
    from xtr_mime import RawMessage

__all__ = ["decrypt", "openssl_verifies", "signed_parts", "verifies", "wire"]

_SHA2: Final = b"\x60\x86\x48\x01\x65\x03\x04\x02"
_HASHES: Final[dict[bytes, type[hashes.HashAlgorithm]]] = {
    _SHA2 + b"\x01": hashes.SHA256,
    _SHA2 + b"\x02": hashes.SHA384,
    _SHA2 + b"\x03": hashes.SHA512,
    _SHA2 + b"\x04": hashes.SHA224,
}
# 1.2.840.113549.1.9.4, the messageDigest attribute.
_MESSAGE_DIGEST: Final = b"\x2a\x86\x48\x86\xf7\x0d\x01\x09\x04"
_SIGNED_ATTRIBUTES: Final = 0xA0
_SET: Final = 0x31
_LONGEST_CHAIN: Final = 5


class _UnverifiedError(Exception):
    """The signature does not hold."""


@dataclass(frozen=True, slots=True)
class _Element:
    """One DER element: its tag, its whole encoding, and its contents."""

    tag: int
    encoded: bytes
    contents: bytes

    def children(self) -> list[_Element]:
        """Read the elements this constructed element holds, in order."""
        items: list[_Element] = []
        offset = 0
        while offset < len(self.contents):
            item, offset = _read(self.contents, offset)
            items.append(item)
        return items


def _read(data: bytes, offset: int = 0) -> tuple[_Element, int]:
    """Read the element at ``offset``; return it and the offset after it."""
    tag, length, start = data[offset], data[offset + 1], offset + 2
    if length & 0x80:
        count = length & 0x7F
        length = int.from_bytes(data[start : start + count], "big")
        start += count
    end = start + length
    if end > len(data):
        raise _UnverifiedError("truncated DER")
    return _Element(tag, data[offset:end], data[start:end]), end


def wire(message: RawMessage) -> bytes:
    """Return the bytes ``message`` is sent as."""
    return b"".join(message.to_iterable())


def signed_parts(sent: bytes) -> tuple[bytes, bytes]:
    """Return the bytes signed, exactly as sent, and the DER signature of a signed message."""
    message = BytesParser(policy=policy.SMTP).parsebytes(sent)
    if message.get_content_type() != "multipart/signed":
        raise _UnverifiedError(f"not a signed message: {message.get_content_type()}")
    delimiter = b"\r\n--" + str(message.get_boundary()).encode("ascii")
    body = b"\r\n" + sent.partition(b"\r\n\r\n")[2]
    start = body.index(delimiter + b"\r\n") + len(delimiter) + 2
    content = body[start : body.index(delimiter, start)]
    signature = list(message.iter_parts())[1].get_payload(decode=True)
    if not isinstance(signature, bytes):
        raise _UnverifiedError("no signature part")
    return content, signature


def verifies(sent: bytes, trusted: x509.Certificate) -> bool:
    """Tell whether the signed message ``sent`` verifies against the CA ``trusted``."""
    try:
        _check(*signed_parts(sent), trusted)
    except (_UnverifiedError, InvalidSignature, ValueError, IndexError, StopIteration):
        return False
    return True


def _check(content: bytes, der: bytes, trusted: x509.Certificate) -> None:
    signed_data = _read(der)[0].children()[1].children()[0].children()
    signer_info = signed_data[-1].children()[0].children()
    serial = int.from_bytes(signer_info[1].children()[1].contents, "big", signed=True)
    algorithm = _HASHES[signer_info[2].children()[0].contents]()
    attributes, signature = signer_info[3], signer_info[5].contents
    if attributes.tag != _SIGNED_ATTRIBUTES:
        raise _UnverifiedError("no signed attributes")
    certificates = pkcs7.load_der_pkcs7_certificates(der)
    certificate = next(item for item in certificates if item.serial_number == serial)
    public_key = certificate.public_key()
    # The signature covers the attributes encoded as the SET they are, not as tagged here.
    signed = bytes([_SET]) + attributes.encoded[1:]
    if isinstance(public_key, rsa.RSAPublicKey):
        public_key.verify(signature, signed, padding.PKCS1v15(), algorithm)
    elif isinstance(public_key, ec.EllipticCurvePublicKey):
        public_key.verify(signature, signed, ec.ECDSA(algorithm))
    else:
        raise _UnverifiedError("unexpected key type")
    digest = hashes.Hash(algorithm)
    digest.update(content)
    if _message_digest(attributes) != digest.finalize():
        raise _UnverifiedError("the signed part does not match the digest signed")
    _check_chain(certificate, [*certificates, trusted], trusted)


def _message_digest(attributes: _Element) -> bytes:
    for attribute in attributes.children():
        oid, values = attribute.children()
        if oid.contents == _MESSAGE_DIGEST:
            return values.children()[0].contents
    raise _UnverifiedError("no message digest")


def _check_chain(
    certificate: x509.Certificate, known: list[x509.Certificate], trusted: x509.Certificate
) -> None:
    current = certificate
    for _ in range(_LONGEST_CHAIN):
        if current == trusted:
            return
        issuer = next(item for item in known if item.subject == current.issuer)
        current.verify_directly_issued_by(issuer)
        current = issuer
    raise _UnverifiedError("the chain does not reach the trusted CA")


def openssl_verifies(sent: bytes, trusted: x509.Certificate, directory: Path) -> bool | None:
    """Ask ``openssl smime -verify`` whether ``sent`` verifies; ``None`` without openssl."""
    openssl = shutil.which("openssl")
    if openssl is None:
        return None
    message, authority = directory / "signed.eml", directory / "ca.pem"
    _ = message.write_bytes(sent)
    _ = authority.write_bytes(trusted.public_bytes(serialization.Encoding.PEM))
    completed = subprocess.run(  # noqa: S603 -- the openssl binary on fixed arguments
        [
            openssl,
            "smime",
            "-verify",
            "-in",
            message,
            "-CAfile",
            authority,
            "-out",
            directory / "out",
        ],
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def decrypt(sent: bytes, identity: Identity) -> bytes:
    """Decrypt the encrypted message ``sent`` with the key of ``identity``."""
    private_key = identity.private_key
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise TypeError("only an RSA key decrypts")
    return pkcs7.pkcs7_decrypt_smime(sent, identity.certificate, private_key, [])
