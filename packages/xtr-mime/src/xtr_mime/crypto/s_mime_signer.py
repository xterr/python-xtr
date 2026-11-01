"""Signs a message's body with S/MIME (RFC 8551), so a receiver can tell who wrote it."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_mime._error_text import escaped
from xtr_mime.exception import InvalidArgumentError, LogicError
from xtr_mime.message import Message
from xtr_mime.part import TextPart

from ._s_mime import read_part, read_pem_file

if TYPE_CHECKING:
    import os

    from ._pkcs7 import Signature

__all__ = ["SMimeSigner"]

_NO_EXTRA: Final = 'The "smime" extra is required to use S/MIME: uv add "xtr-mime[smime]".'


@final
class SMimeSigner:
    """Signs messages with one certificate and its private key, the signature detached.

    :meth:`sign` renders the message's body once and returns a message whose body is a
    ``multipart/signed`` part: the body as it was signed, then the signature — readable by a
    client that cannot check it. The message's headers stay outside the signature, as they are.

    The certificates and the key are read from PEM files when the signer is built. Needs the
    ``smime`` extra (``xtr-mime[smime]``: cryptography).
    """

    ALGO_SHA224: ClassVar[str] = "sha224"
    ALGO_SHA256: ClassVar[str] = "sha256"
    ALGO_SHA384: ClassVar[str] = "sha384"
    ALGO_SHA512: ClassVar[str] = "sha512"

    __slots__ = ("_signature",)

    def __init__(
        self,
        certificate: str | os.PathLike[str],
        private_key: str | os.PathLike[str],
        *,
        passphrase: str = "",
        extra_certificates: str | os.PathLike[str] | None = None,
        algorithm: str = ALGO_SHA256,
    ) -> None:
        """Read the certificate and open the key now, so one that does not work fails here.

        Args:
            certificate: The path of the signing certificate's PEM file; a string may start
                with ``file://``.
            private_key: The path of the PEM file of the certificate's private key, RSA or EC.
                An RSA key has at least 1024 bits, and its certificate is not for RSA-PSS:
                the signature is made with PKCS #1 v1.5 padding.
            passphrase: The passphrase of an encrypted key; empty for one that is not — a
                passphrase given for a key that is not encrypted is refused.
            extra_certificates: The path of a PEM file of the intermediate certificates a
                receiver needs to follow the signing certificate up to one it trusts.
            algorithm: The digest signed, one of the ``ALGO_*`` names.

        Raises:
            LogicError: The ``smime`` extra is not installed.
            InvalidArgumentError: The algorithm is not one of the ``ALGO_*`` names, a
                certificate or the key does not load, the key is neither RSA nor EC, an RSA
                key is shorter than 1024 bits or certified for RSA-PSS, or the key is not the
                certificate's.
            MimeRuntimeError: A file does not exist or cannot be read, or a path is not one
                the file system accepts.
        """
        try:
            from ._pkcs7 import (  # noqa: PLC0415 -- the smime extra is optional.
                Signature,
                load_certificates,
                load_key_pair,
            )
        except ImportError as error:
            raise LogicError(_NO_EXTRA) from error
        if algorithm not in {
            self.ALGO_SHA224,
            self.ALGO_SHA256,
            self.ALGO_SHA384,
            self.ALGO_SHA512,
        }:
            raise InvalidArgumentError(f'Invalid S/MIME signing algorithm "{escaped(algorithm)}".')
        signer, key = load_key_pair(
            read_pem_file(certificate), read_pem_file(private_key), passphrase
        )
        extra = (
            ()
            if extra_certificates is None
            else tuple(load_certificates(read_pem_file(extra_certificates)))
        )
        self._signature: Signature = Signature(signer, key, extra, algorithm)

    def sign(self, message: Message) -> Message:
        """Return a message with the headers of ``message`` and its body signed.

        ``message`` is left as it is; a stream body is read here, once. A message without a
        body is signed with the empty text it renders with. A Date or Message-ID that sending
        adds is added to the headers returned too — the Date read from the clock of
        ``message`` — so the signed message renders the same every time.

        Raises:
            LogicError: As rendering the body does, or the message has neither a From nor a
                Sender to send it with.
            RfcComplianceError: As rendering the body does.
        """
        headers = copy.copy(message.get_headers())
        prepared = message.get_prepared_headers()
        for name in ("Date", "Message-ID"):
            added = prepared.get(name)
            if added is not None and not headers.has(name):
                _ = headers.add(added)
        body = message.get_body() or TextPart("")
        signed = self._signature.sign(b"".join(body.to_iterable()))
        return Message(headers, read_part(signed))
