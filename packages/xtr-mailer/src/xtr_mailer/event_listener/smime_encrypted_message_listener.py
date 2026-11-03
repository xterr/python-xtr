"""Encrypts an email that asks for it with S/MIME, for its recipients' certificates."""

from __future__ import annotations

import copy
from importlib.util import find_spec
from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_logging_contracts import NullLogger
from xtr_mime import Message
from xtr_mime.crypto import SMimeEncrypter

from xtr_mailer._error_text import shown
from xtr_mailer._on_missing_certificate import ENCRYPT, FAIL, MODES, SKIP, checked_mode
from xtr_mailer.exception import LogicError, MailerRuntimeError

if TYPE_CHECKING:
    from xtr_logging_contracts import LoggerInterface

    from xtr_mailer.envelope import Envelope
    from xtr_mailer.event import MessageEvent

    from .smime_certificate_repository_interface import SmimeCertificateRepositoryInterface

__all__ = ["SmimeEncryptedMessageListener"]

_HEADER: Final = "X-SMime-Encrypt"
_NO_EXTRA: Final = 'The "smime" extra is required to use S/MIME: uv add "xtr-mailer[smime]".'
_NONE_FOUND: Final = "No S/MIME certificate found for any recipient."


@final
class SmimeEncryptedMessageListener:
    """Encrypts each email carrying an ``X-SMime-Encrypt`` header for its envelope recipients.

    Listen to :class:`~xtr_mailer.event.MessageEvent` with :meth:`on_message` at
    :attr:`PRIORITY`: after the S/MIME signing listener, so a signed email is encrypted
    whole, and before the DKIM listener, whose signature covers the encrypted email. An email
    without the header, and raw bytes, are sent as they are.

    Each envelope recipient's certificate — hidden recipients included — is looked up in the
    repository by its bare address. What happens when a recipient has none is the
    ``on_missing_certificate`` mode, which the header's value overrides when it names one:

    - ``fail``: the email is refused, naming the recipients without a certificate.
    - ``encrypt``: the email is encrypted for the recipients with one; the others still
      receive it, unreadable.
    - ``skip``: as ``encrypt``, and the others are dropped from the envelope.

    Whatever the mode, an email no recipient has a certificate for is refused, and a missing
    certificate is logged as a warning. The encrypted email keeps the headers of the email
    given, Bcc among them, but the ``X-SMime-Encrypt`` header, which is neither sent nor
    encrypted; the email given is left as it is.
    """

    #: Run after the email is signed with S/MIME, before it is signed with DKIM.
    PRIORITY: Final = -200

    #: Refuse the email when a recipient has no certificate.
    ON_MISSING_CERTIFICATE_FAIL: Final = FAIL
    #: Encrypt for the recipients with a certificate; the others still receive the email.
    ON_MISSING_CERTIFICATE_ENCRYPT: Final = ENCRYPT
    #: Encrypt for the recipients with a certificate and drop the others from the envelope.
    ON_MISSING_CERTIFICATE_SKIP: Final = SKIP

    __slots__: ClassVar[tuple[str, ...]] = (
        "_cipher",
        "_encrypt_for_sender",
        "_logger",
        "_on_missing_certificate",
        "_repository",
    )

    def __init__(
        self,
        repository: SmimeCertificateRepositoryInterface,
        cipher: str = SMimeEncrypter.CIPHER_AES_256_CBC,
        on_missing_certificate: str = ON_MISSING_CERTIFICATE_FAIL,
        encrypt_for_sender: bool = False,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Encrypt for the certificates ``repository`` finds.

        Args:
            repository: Finds each recipient's certificate by address.
            cipher: The cipher the email is encrypted with, one of
                :class:`~xtr_mime.crypto.SMimeEncrypter`'s ``CIPHER_*`` names; one it does
                not support is refused when an email is encrypted.
            on_missing_certificate: What to do when a recipient has no certificate, one of
                the ``ON_MISSING_CERTIFICATE_*`` modes.
            encrypt_for_sender: Encrypt for the envelope sender's certificate too, when the
                repository has one, so the sender can read what was sent.
            logger: Where a recipient without a certificate is reported; ``None`` logs
                nothing.

        Raises:
            LogicError: The ``smime`` extra is not installed.
            InvalidArgumentError: ``on_missing_certificate`` is not one of the modes, or not a
                string.
        """
        if find_spec("cryptography") is None:
            raise LogicError(_NO_EXTRA)
        self._repository: SmimeCertificateRepositoryInterface = repository
        self._cipher: str = cipher
        self._on_missing_certificate: str = checked_mode(on_missing_certificate)
        self._encrypt_for_sender: bool = encrypt_for_sender
        self._logger: LoggerInterface = logger if logger is not None else NullLogger()

    def on_message(self, event: MessageEvent) -> None:
        """Replace ``event``'s email with the encrypted one, when it asks to be encrypted.

        Raises:
            MailerRuntimeError: A recipient has no certificate in ``fail`` mode, or no
                recipient has one.
            xtr_mime.MimeError: As encrypting does — a certificate does not load, the cipher
                is not supported, the email does not render.
        """
        message = event.get_message()
        if not isinstance(message, Message):
            return
        header = message.get_headers().get(_HEADER)
        if header is None:
            return
        mode = header.get_body_as_string()
        if mode not in MODES:
            mode = self._on_missing_certificate
        envelope = event.get_envelope()
        certificates = self._certificates(envelope, mode)
        if self._encrypt_for_sender:
            sender = envelope.get_sender().get_address()
            if (path := self._repository.find_certificate_path_for(sender)) is not None:
                certificates[sender] = path
        unmarked = copy.copy(message)
        unmarked.get_headers().remove(_HEADER)
        encrypter = SMimeEncrypter(list(certificates.values()), self._cipher)
        event.set_message(encrypter.encrypt(unmarked))

    def _certificates(self, envelope: Envelope, mode: str) -> dict[str, str]:
        """Return the recipients' certificate paths by address, dropping the others in skip.

        Raises:
            MailerRuntimeError: A recipient has none in ``fail`` mode, or none has one.
        """
        certificates: dict[str, str] = {}
        missing: list[str] = []
        for recipient in envelope.get_recipients():
            address = recipient.get_address()
            path = self._repository.find_certificate_path_for(address)
            if path is None:
                missing.append(address)
            else:
                certificates[address] = path
        if missing:
            if mode == self.ON_MISSING_CERTIFICATE_FAIL:
                listed = '", "'.join(shown(address) for address in missing)
                raise MailerRuntimeError(
                    f'No S/MIME certificate found for recipient(s) "{listed}".'
                )
            self._logger.warning(
                "Some recipients have no S/MIME certificate.",
                {"recipients": missing, "on_missing_certificate": mode},
            )
        if not certificates:
            raise MailerRuntimeError(_NONE_FOUND)
        if missing and mode == self.ON_MISSING_CERTIFICATE_SKIP:
            envelope.set_recipients(
                recipient
                for recipient in envelope.get_recipients()
                if recipient.get_address() in certificates
            )
        return certificates
