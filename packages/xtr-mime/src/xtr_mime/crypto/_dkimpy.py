"""The one module importing the dkim extra: cryptography opens the key, dkimpy signs with it.

Importing it without the extra raises ``ImportError``; :class:`~xtr_mime.crypto.DkimSigner`
turns that into an error naming the extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

import dkim
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from xtr_mime._error_text import escaped
from xtr_mime.exception import InvalidArgumentError, MimeRuntimeError

__all__ = ["SignatureRequest", "load_private_key", "sign"]

_KEY_ERROR = "Unable to load DKIM private key: "
# RFC 8301, 3.2: a verifier refuses a signature made with a shorter RSA key.
_MIN_KEY_SIZE = 1024


@final
@dataclass(frozen=True, slots=True)
class SignatureRequest:
    """What a signature is made with, the message aside; names are ASCII, checked before."""

    selector: str
    domain_name: str
    private_key: bytes
    """An unencrypted RSA key in traditional PEM, as :func:`load_private_key` returns it."""
    canonicalization: tuple[str, str]
    """Header canonicalization, then body canonicalization."""
    header_names: tuple[str, ...]
    """The headers signed, a name once per field of that name."""
    show_body_length: bool


def load_private_key(pem: bytes, passphrase: str) -> bytes:
    """Open the RSA key in ``pem``, decrypting it with ``passphrase`` when it is not empty.

    dkimpy reads only an unencrypted traditional (``BEGIN RSA PRIVATE KEY``) PEM, so the key
    is handed on in that form, decrypted in memory. cryptography's own reason for refusing a
    key names the problem, never the key.

    The passphrase is encoded as the file system encodes a name: one read from the command
    line or the environment with bytes that are not UTF-8 holds them as surrogates, and opens
    the key with those bytes. A passphrase given for a key that is not encrypted is refused,
    as cryptography refuses it.

    Raises:
        InvalidArgumentError: The key does not open — not PEM, encrypted and the passphrase
            missing, wrong or not text at all, a passphrase given for a key that is not
            encrypted — or it is not an RSA key of at least 1024 bits. The passphrase is in no
            error of the chain.
    """
    try:
        secret: bytes | None = passphrase.encode("utf-8", "surrogateescape") or None
        encodable = True
    except UnicodeEncodeError:
        # Raised outside this block: the codec's error holds the whole passphrase, and an
        # error raised here would carry it as its context.
        secret, encodable = None, False
    if not encodable:
        raise InvalidArgumentError(f"{_KEY_ERROR}the passphrase is not text that can be encoded.")
    try:
        key = serialization.load_pem_private_key(pem, secret)
    except (TypeError, ValueError, UnsupportedAlgorithm) as error:
        raise InvalidArgumentError(f"{_KEY_ERROR}{escaped(str(error))}") from error
    if not isinstance(key, rsa.RSAPrivateKey):
        raise InvalidArgumentError(f'{_KEY_ERROR}only an RSA key signs "rsa-sha256".')
    if key.key_size < _MIN_KEY_SIZE:
        raise InvalidArgumentError(
            f"{_KEY_ERROR}the RSA key has {key.key_size} bits; a DKIM verifier needs at least "
            f"{_MIN_KEY_SIZE}."
        )
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )


def sign(message: bytes, request: SignatureRequest) -> str:
    """Sign the rendered ``message`` and return its DKIM-Signature field, folded, ending in CRLF.

    dkimpy refuses to sign the headers RFC 6376 advises a signer to leave out (Received,
    Comments); here a header is signed unless the caller said to ignore it — the signer
    never names a DKIM-Signature already there.

    Raises:
        MimeRuntimeError: dkimpy refuses to sign: the message has no From to sign.
    """
    signer = dkim.DKIM(message)
    signer.should_not_sign = set()
    header_canon, body_canon = request.canonicalization
    try:
        field = signer.sign(
            request.selector.encode("ascii"),
            request.domain_name.encode("ascii"),
            request.private_key,
            canonicalize=(header_canon.encode("ascii"), body_canon.encode("ascii")),
            include_headers=[name.encode("ascii") for name in request.header_names],
            length=request.show_body_length,
        )
    except dkim.DKIMException as error:
        raise MimeRuntimeError(f"Unable to sign DKIM hash: {escaped(str(error))}") from error
    return field.decode("ascii")
