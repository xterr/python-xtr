"""The listener encrypting an email that asks for it for the recipients' S/MIME certificates.

Upstream's test of the mode sending the email unencrypted when a recipient has no certificate
is not ported: that mode is not carried. Its default here is ``fail``, so the test of the
header overriding the default overrides ``encrypt``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_logging_contracts import AbstractLogger, Level
from xtr_mime import Address, Message
from xtr_mime.header import Headers
from xtr_mime.part import SMimePart, TextPart

from tests.support.smime_identities import identity
from xtr_mailer import Envelope
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import (
    DkimSignedMessageListener,
    InMemorySmimeCertificateRepository,
    SmimeEncryptedMessageListener,
    SmimeSignedMessageListener,
)
from xtr_mailer.exception import MailerRuntimeError

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_logging_contracts import Context, LevelLike

_Listener = SmimeEncryptedMessageListener
_MISSING_R2 = 'No S/MIME certificate found for recipient(s) "r2@example.com".'
_NONE_FOUND = "No S/MIME certificate found for any recipient."


class _RecordingLogger(AbstractLogger):
    def __init__(self) -> None:
        self.records: list[tuple[LevelLike, str, Context | None]] = []

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        self.records.append((level, message, context))


def _repository(directory: Path, *addresses: str) -> InMemorySmimeCertificateRepository:
    return InMemorySmimeCertificateRepository(
        {address: str(identity(address).write(directory, address)[0]) for address in addresses}
    )


def _message(encrypt: str | None = "true") -> Message:
    headers = Headers().add_mailbox_list_header("From", ["sender@example.com"])
    if encrypt is not None:
        _ = headers.add_text_header("X-SMime-Encrypt", encrypt)
    return Message(headers, TextPart("hello"))


def _event(message: Message, *recipients: str) -> MessageEvent:
    envelope = Envelope(
        Address("sender@example.com"),
        [Address(recipient) for recipient in recipients or ("r1@example.com", "r2@example.com")],
    )
    return MessageEvent(message, envelope, "default")


def _recipients(event: MessageEvent) -> list[str]:
    return [recipient.get_address() for recipient in event.get_envelope().get_recipients()]


def test_smime_message_encryption_process(tmp_path: Path) -> None:
    message = _message()
    event = _event(message, "r1@example.com")

    _Listener(_repository(tmp_path, "r1@example.com")).on_message(event)

    encrypted = event.get_message()
    assert encrypted is not message
    assert isinstance(message.get_body(), TextPart)
    assert isinstance(encrypted, Message)
    assert isinstance(encrypted.get_body(), SMimePart)
    assert not encrypted.get_headers().has("X-SMime-Encrypt")


def test_message_not_explicitly_asked_for_non_encryption(tmp_path: Path) -> None:
    message = _message(encrypt=None)
    event = _event(message)

    _Listener(_repository(tmp_path, "r1@example.com", "r2@example.com")).on_message(event)

    assert event.get_message() is message
    assert isinstance(message.get_body(), TextPart)


def test_fail_mode_throws_when_a_recipient_has_no_certificate(tmp_path: Path) -> None:
    listener = _Listener(_repository(tmp_path, "r1@example.com"), on_missing_certificate="fail")

    with pytest.raises(MailerRuntimeError) as raised:
        listener.on_message(_event(_message()))

    assert str(raised.value) == _MISSING_R2


def test_fail_is_the_default_mode(tmp_path: Path) -> None:
    with pytest.raises(MailerRuntimeError) as raised:
        _Listener(_repository(tmp_path, "r1@example.com")).on_message(_event(_message()))

    assert str(raised.value) == _MISSING_R2


def test_encrypt_mode_encrypts_for_recipients_with_certificate(tmp_path: Path) -> None:
    event = _event(_message())
    listener = _Listener(
        _repository(tmp_path, "r1@example.com"),
        on_missing_certificate=_Listener.ON_MISSING_CERTIFICATE_ENCRYPT,
    )

    listener.on_message(event)

    encrypted = event.get_message()
    assert isinstance(encrypted, Message)
    assert isinstance(encrypted.get_body(), SMimePart)
    assert _recipients(event) == ["r1@example.com", "r2@example.com"]


def test_skip_mode_drops_recipients_without_certificate(tmp_path: Path) -> None:
    event = _event(_message())
    repository = _repository(tmp_path, "r1@example.com")

    _Listener(repository, on_missing_certificate=_Listener.ON_MISSING_CERTIFICATE_SKIP).on_message(
        event
    )

    encrypted = event.get_message()
    assert isinstance(encrypted, Message)
    assert isinstance(encrypted.get_body(), SMimePart)
    assert _recipients(event) == ["r1@example.com"]


def test_header_value_overrides_the_default_behavior(tmp_path: Path) -> None:
    repository = _repository(tmp_path, "r1@example.com")
    listener = _Listener(repository, on_missing_certificate="encrypt")

    with pytest.raises(MailerRuntimeError) as raised:
        listener.on_message(_event(_message(_Listener.ON_MISSING_CERTIFICATE_FAIL)))

    assert str(raised.value) == _MISSING_R2


@pytest.mark.parametrize("mode", ["encrypt", "skip"])
def test_a_mode_throws_when_no_recipient_has_certificate(mode: str) -> None:
    listener = _Listener(InMemorySmimeCertificateRepository(), on_missing_certificate=mode)

    with pytest.raises(MailerRuntimeError) as raised:
        listener.on_message(_event(_message(), "r1@example.com"))

    assert str(raised.value) == _NONE_FOUND


class _QueriedRepository:
    def __init__(self, path: str) -> None:
        self.path: str = path
        self.queried: list[str] = []

    def find_certificate_path_for(self, email: str) -> str | None:
        self.queried.append(email)
        return self.path


@pytest.mark.parametrize("encrypt_for_sender", [True, False])
def test_the_sender_certificate_is_looked_up_only_when_encrypting_for_the_sender(
    encrypt_for_sender: bool, tmp_path: Path
) -> None:
    certificate = identity("r1@example.com").write(tmp_path, "r1")[0]
    repository = _QueriedRepository(str(certificate))
    event = _event(_message(), "r1@example.com")

    _Listener(repository, encrypt_for_sender=encrypt_for_sender).on_message(event)

    encrypted = event.get_message()
    assert isinstance(encrypted, Message)
    assert isinstance(encrypted.get_body(), SMimePart)
    assert ("sender@example.com" in repository.queried) is encrypt_for_sender


def test_the_header_is_kept_when_the_message_is_not_sent() -> None:
    message = _message()

    with pytest.raises(MailerRuntimeError):
        _Listener(InMemorySmimeCertificateRepository()).on_message(_event(message))

    assert message.get_headers().has("X-SMime-Encrypt")


def test_header_cannot_downgrade_to_send_unencrypted(tmp_path: Path) -> None:
    listener = _Listener(_repository(tmp_path, "r1@example.com"), on_missing_certificate="fail")

    with pytest.raises(MailerRuntimeError) as raised:
        listener.on_message(_event(_message("send_unencrypted")))

    assert str(raised.value) == _MISSING_R2


def test_missing_recipients_are_logged(tmp_path: Path) -> None:
    logger = _RecordingLogger()
    listener = _Listener(
        _repository(tmp_path, "r1@example.com"), on_missing_certificate="encrypt", logger=logger
    )
    event = _event(_message())

    listener.on_message(event)

    assert logger.records == [
        (
            Level.WARNING,
            "Some recipients have no S/MIME certificate.",
            {"recipients": ["r2@example.com"], "on_missing_certificate": "encrypt"},
        )
    ]
    encrypted = event.get_message()
    assert isinstance(encrypted, Message)
    assert isinstance(encrypted.get_body(), SMimePart)


def test_encryption_runs_after_signing() -> None:
    assert SmimeSignedMessageListener.PRIORITY > SmimeEncryptedMessageListener.PRIORITY
    assert SmimeEncryptedMessageListener.PRIORITY > DkimSignedMessageListener.PRIORITY
    assert SmimeEncryptedMessageListener.PRIORITY == -200
