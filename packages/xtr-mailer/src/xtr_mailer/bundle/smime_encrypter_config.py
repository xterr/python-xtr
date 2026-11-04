"""The S/MIME encryption of every email asking for it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, final

from xtr_dependency_injection import Reference
from xtr_mime.crypto import SMimeEncrypter

from xtr_mailer._error_text import shown
from xtr_mailer._on_missing_certificate import FAIL, checked_mode
from xtr_mailer.exception import InvalidArgumentError

__all__ = ["SmimeEncrypterConfig"]

_SUPPORTED: Final = (SMimeEncrypter.CIPHER_AES_128_CBC, SMimeEncrypter.CIPHER_AES_256_CBC)
_UNSUPPORTED: Final = (
    SMimeEncrypter.CIPHER_RC2_40,
    SMimeEncrypter.CIPHER_RC2_64,
    SMimeEncrypter.CIPHER_RC2_128,
    SMimeEncrypter.CIPHER_DES,
    SMimeEncrypter.CIPHER_3DES,
    SMimeEncrypter.CIPHER_AES_192_CBC,
)


def _no_certificates() -> dict[str, str]:
    """The empty certificate map of an encrypter reading a repository service instead."""
    return {}


@final
@dataclass(frozen=True, slots=True)
class SmimeEncrypterConfig:
    """Encrypts each email carrying an ``X-SMime-Encrypt`` header. Needs the ``smime`` extra.

    The recipients' certificates come from ``certificates``, or from a repository service the
    application registers — one or the other.

    Attributes:
        repository: The :class:`~xtr_mailer.event_listener.SmimeCertificateRepositoryInterface`
            service finding each recipient's certificate, by its type and qualifier.
        certificates: The path of each recipient's certificate, by address.
        cipher: ``aes-128-cbc`` or ``aes-256-cbc``.
        on_missing_certificate: What to do with a recipient without a certificate: ``fail``
            refuses the email, ``encrypt`` sends it unreadable to that recipient, ``skip``
            drops the recipient.
        encrypt_for_sender: Encrypt for the envelope sender's certificate too, when there is
            one, so the sender can read what was sent.
    """

    repository: Reference | None = None
    certificates: Mapping[str, str] = field(default_factory=_no_certificates)
    cipher: str = SMimeEncrypter.CIPHER_AES_256_CBC
    on_missing_certificate: str = FAIL
    encrypt_for_sender: bool = False

    def __post_init__(self) -> None:
        """Refuse two sources of certificates or none, an unknown mode and a cipher not usable.

        Raises:
            InvalidArgumentError: Both or neither of ``repository`` and ``certificates`` are
                given, the repository's qualifier is not a string, the mode is unknown, or the
                cipher is not one the encrypter supports.
        """
        if self.repository is not None and self.certificates:
            raise InvalidArgumentError('"repository" and "certificates" cannot be used together.')
        if self.repository is None and not self.certificates:
            raise InvalidArgumentError(
                'The S/MIME encrypter needs a "repository" or "certificates".'
            )
        if self.repository is not None and not isinstance(self.repository.qualifier, str | None):
            raise InvalidArgumentError('The S/MIME "repository" qualifier must be a string.')
        _ = checked_mode(self.on_missing_certificate)
        _check_cipher(self.cipher)


def _check_cipher(cipher: object) -> None:
    """Refuse a cipher the encrypter does not support, saying which it does.

    Raises:
        InvalidArgumentError: ``cipher`` is not ``aes-128-cbc`` or ``aes-256-cbc``.
    """
    if not isinstance(cipher, str):
        raise InvalidArgumentError(
            f'Invalid S/MIME cipher (got a value of type "{type(cipher).__name__}").'
        )
    if cipher in _SUPPORTED:
        return
    if cipher in _UNSUPPORTED:
        raise InvalidArgumentError(
            f'The "{cipher}" S/MIME cipher is not supported; use "aes-128-cbc" or "aes-256-cbc".'
        )
    raise InvalidArgumentError(f'Invalid S/MIME cipher "{shown(cipher)}".')
