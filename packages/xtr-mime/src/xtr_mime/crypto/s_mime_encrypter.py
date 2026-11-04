"""Encrypts a whole message with S/MIME (RFC 8551), so only its recipients can read it."""

from __future__ import annotations

import copy
import os
from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_mime._error_text import escaped
from xtr_mime.exception import InvalidArgumentError, LogicError
from xtr_mime.message import Message

from ._s_mime import read_part, read_pem_file

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ._pkcs7 import Envelope

__all__ = ["SMimeEncrypter"]

_NO_EXTRA: Final = 'The "smime" extra is required to use S/MIME: uv add "xtr-mime[smime]".'


@final
class SMimeEncrypter:
    """Encrypts messages for one or several recipients, each with a certificate of its own.

    :meth:`encrypt` renders the whole message once — its headers included — and returns a
    message whose body is that rendering encrypted, an ``application/pkcs7-mime`` attachment
    any recipient's key decrypts back to the very bytes rendered. The headers stay outside,
    readable, so that the message can be delivered.

    The certificates are read from PEM files when the encrypter is built. Needs the ``smime``
    extra (``xtr-mime[smime]``: cryptography), which encrypts with AES in CBC mode only: the
    other ``CIPHER_*`` names are refused.
    """

    CIPHER_RC2_40: ClassVar[str] = "rc2-40"
    CIPHER_RC2_128: ClassVar[str] = "rc2-128"
    CIPHER_RC2_64: ClassVar[str] = "rc2-64"
    CIPHER_DES: ClassVar[str] = "des"
    CIPHER_3DES: ClassVar[str] = "3des"
    CIPHER_AES_128_CBC: ClassVar[str] = "aes-128-cbc"
    CIPHER_AES_192_CBC: ClassVar[str] = "aes-192-cbc"
    CIPHER_AES_256_CBC: ClassVar[str] = "aes-256-cbc"

    __slots__ = ("_envelope",)

    def __init__(
        self,
        certificates: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
        cipher: str = CIPHER_AES_256_CBC,
    ) -> None:
        """Read the recipients' certificates now, so one that does not work fails here.

        Args:
            certificates: The path of a recipient's PEM certificate, or the paths of
                several; a string may start with ``file://``.
            cipher: The cipher the message is encrypted with, one of the ``CIPHER_*`` names
                cryptography supports: ``aes-128-cbc`` or ``aes-256-cbc``.

        Raises:
            LogicError: The ``smime`` extra is not installed.
            InvalidArgumentError: The cipher is unknown or not supported, no certificate is
                given, or one or its key does not load, or its key is not RSA.
            MimeRuntimeError: A file does not exist or cannot be read, or a path is not one
                the file system accepts.
        """
        try:
            from ._pkcs7 import (  # noqa: PLC0415 -- the smime extra is optional.
                Envelope,
                load_recipient,
            )
        except ImportError as error:
            raise LogicError(_NO_EXTRA) from error
        _check_cipher(cipher)
        paths = (
            [certificates] if isinstance(certificates, (str, os.PathLike)) else list(certificates)
        )
        if not paths:
            raise InvalidArgumentError(
                "At least one certificate is required to encrypt with S/MIME."
            )
        recipients = tuple(load_recipient(read_pem_file(path)) for path in paths)
        self._envelope: Envelope = Envelope(recipients, cipher)

    def encrypt(self, message: Message) -> Message:
        """Return a message with the headers of ``message`` and the whole of it encrypted.

        ``message`` is left as it is, rendered here once, as it is sent: without Bcc. A Date or
        Message-ID that sending adds is added to the headers returned too, so the message
        delivered names the one it holds.

        Raises:
            LogicError: As rendering the message does.
            RfcComplianceError: As rendering the message does.
        """
        headers = copy.copy(message.get_headers())
        prepared = message.get_prepared_headers()
        for name in ("Date", "Message-ID"):
            added = prepared.get(name)
            if added is not None and not headers.has(name):
                _ = headers.add(added)
        # The body itself, not a copy: a copied multipart would make up a boundary of its own.
        sent = copy.copy(message).set_headers(copy.copy(headers)).set_body(message.get_body())
        part = read_part(self._envelope.encrypt(b"".join(sent.to_iterable())))
        _ = (
            part.get_headers()
            .add_text_header("Content-Transfer-Encoding", "base64")
            .add_parameterized_header(
                "Content-Disposition", "attachment", {"filename": "smime.p7m"}
            )
        )
        return Message(headers, part)


def _check_cipher(cipher: str) -> None:
    supported = {SMimeEncrypter.CIPHER_AES_128_CBC, SMimeEncrypter.CIPHER_AES_256_CBC}
    if cipher in supported:
        return
    known = {
        SMimeEncrypter.CIPHER_RC2_40,
        SMimeEncrypter.CIPHER_RC2_128,
        SMimeEncrypter.CIPHER_RC2_64,
        SMimeEncrypter.CIPHER_DES,
        SMimeEncrypter.CIPHER_3DES,
        SMimeEncrypter.CIPHER_AES_192_CBC,
    }
    if cipher in known:
        raise InvalidArgumentError(
            f'The "{cipher}" S/MIME cipher is not supported; use "aes-128-cbc" or "aes-256-cbc".'
        )
    raise InvalidArgumentError(f'Invalid S/MIME cipher "{escaped(cipher)}".')
