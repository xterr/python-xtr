"""An S/MIME encrypter turns a whole message into an enveloped part only its recipients read.

Every message is decrypted back with cryptography, by each recipient's key, and compared with
what the message sends.
"""

from __future__ import annotations

import base64
import sys
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from typing import TYPE_CHECKING

import pytest

from tests.support.smime_extra import require_smime_extra

require_smime_extra()

# Imported after the skip: without the extra these modules do not import.
from tests.support.smime_certificates import (  # noqa: E402 -- see above.
    authority,
    ec_signer,
    other_recipient,
    recipient,
    unsupported_key_certificate_pem,
)
from tests.support.smime_checks import decrypt, verifies, wire  # noqa: E402 -- see above.
from tests.support.smime_signing import (  # noqa: E402 -- see above.
    assert_headers_kept,
    email,
    encrypter,
    signer,
)
from xtr_mime import (  # noqa: E402 -- see above.
    Address,
    DataPart,
    Email,
    Headers,
    InvalidArgumentError,
    LogicError,
    Message,
    MimeRuntimeError,
    MixedPart,
    TextPart,
)
from xtr_mime.crypto import SMimeEncrypter  # noqa: E402 -- see above.

if TYPE_CHECKING:
    from pathlib import Path

_AES_CBC = b"\x60\x86\x48\x01\x65\x03\x04\x01"


def _assert_encrypted(encrypted: Message, original: Message) -> None:
    sent = wire(encrypted)
    assert b"\r\n" in sent
    assert b"\n" not in sent.replace(b"\r\n", b"")
    assert_headers_kept(encrypted, original)
    assert decrypt(sent, recipient()) == wire(original)


def _enveloped_der(encrypted: Message) -> bytes:
    payload = BytesParser(policy=policy.SMTP).parsebytes(wire(encrypted)).get_payload()
    assert isinstance(payload, str)
    return base64.b64decode(payload)


def test_an_encrypted_message_decrypts_to_the_message_as_sent(tmp_path: Path) -> None:
    original = email()

    encrypted = encrypter(tmp_path).encrypt(original)

    _assert_encrypted(encrypted, original)


def test_a_signed_message_encrypted_decrypts_to_the_signed_message(tmp_path: Path) -> None:
    original = email().bcc("luna@example.com")
    signed = signer(tmp_path).sign(original)

    encrypted = encrypter(tmp_path).encrypt(signed)

    _assert_encrypted(encrypted, signed)
    assert verifies(decrypt(wire(encrypted), recipient()), authority().certificate)


def test_each_recipient_decrypts_a_message_encrypted_for_several(tmp_path: Path) -> None:
    to_fabien = email()
    to_luna = email("luna@example.com", "some@id2")
    both = encrypter(tmp_path, recipient(), other_recipient())

    encrypted = [both.encrypt(to_fabien), both.encrypt(to_luna)]

    for result, original in zip(encrypted, (to_fabien, to_luna), strict=True):
        _assert_encrypted(result, original)
        assert decrypt(wire(result), other_recipient()) == wire(original)


def test_a_recipient_the_message_is_not_for_cannot_decrypt(tmp_path: Path) -> None:
    encrypted = encrypter(tmp_path).encrypt(email())

    with pytest.raises(ValueError, match="No recipient found"):
        _ = decrypt(wire(encrypted), other_recipient())


def test_the_body_is_an_enveloped_attachment(tmp_path: Path) -> None:
    encrypted = encrypter(tmp_path).encrypt(email())

    body = encrypted.get_body()
    assert body is not None
    headers = body.get_prepared_headers()
    assert headers.get_header_body("Content-Type") == "application/pkcs7-mime"
    assert headers.get_header_parameter("Content-Type", "smime-type") == "enveloped-data"
    assert headers.get_header_parameter("Content-Type", "name") == "smime.p7m"
    assert headers.get_header_body("Content-Transfer-Encoding") == "base64"
    assert headers.get_header_body("Content-Disposition") == "attachment"
    assert headers.get_header_parameter("Content-Disposition", "filename") == "smime.p7m"


def test_a_message_with_non_ascii_headers_and_an_attachment_decrypts(tmp_path: Path) -> None:
    headers = (
        Headers()
        .add_date_header("Date", datetime(2019, 4, 7, tzinfo=UTC))
        .add_mailbox_list_header("From", [Address("fabien@example.com", "Fabién Pötencier")])
        .add_mailbox_list_header("To", ["luna@example.com"])
        .add_text_header("Subject", "Grüße — ça va?")
        .add_id_header("Message-ID", "some@id")
    )
    attachment = DataPart("ünïcödé ✓".encode(), "naïve.txt", "text/plain")
    original = Message(headers, MixedPart(TextPart("Héllo"), attachment))

    encrypted = encrypter(tmp_path).encrypt(original)

    _assert_encrypted(encrypted, original)


@pytest.mark.parametrize(
    ("cipher", "oid_end"),
    [(None, b"\x2a"), ("aes-256-cbc", b"\x2a"), ("aes-128-cbc", b"\x02")],
)
def test_the_cipher_asked_for_encrypts(tmp_path: Path, cipher: str | None, oid_end: bytes) -> None:
    certificate = recipient().write(tmp_path, "encrypt")[0]
    built = SMimeEncrypter(certificate) if cipher is None else SMimeEncrypter(certificate, cipher)
    original = email()

    encrypted = built.encrypt(original)

    assert b"\x06\x09" + _AES_CBC + oid_end in _enveloped_der(encrypted)
    _assert_encrypted(encrypted, original)


@pytest.mark.parametrize(
    "cipher",
    [
        SMimeEncrypter.CIPHER_RC2_40,
        SMimeEncrypter.CIPHER_RC2_128,
        SMimeEncrypter.CIPHER_RC2_64,
        SMimeEncrypter.CIPHER_DES,
        SMimeEncrypter.CIPHER_3DES,
        SMimeEncrypter.CIPHER_AES_192_CBC,
    ],
)
def test_a_cipher_cryptography_cannot_encrypt_with_is_refused(tmp_path: Path, cipher: str) -> None:
    certificate = recipient().write(tmp_path, "encrypt")[0]

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeEncrypter(certificate, cipher)

    assert str(raised.value) == (
        f'The "{cipher}" S/MIME cipher is not supported; use "aes-128-cbc" or "aes-256-cbc".'
    )


def test_an_unknown_cipher_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeEncrypter(tmp_path / "missing.crt", "rot13")

    assert str(raised.value) == 'Invalid S/MIME cipher "rot13".'


def test_a_certificate_without_an_rsa_key_is_refused(tmp_path: Path) -> None:
    certificate = ec_signer().write(tmp_path, "elliptic")[0]

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeEncrypter(certificate)

    assert str(raised.value) == (
        f'The S/MIME certificate "{certificate}" holds a key that is not RSA: a message is '
        "encrypted only for an RSA key."
    )


def test_no_certificate_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeEncrypter([])

    assert str(raised.value) == "At least one certificate is required to encrypt with S/MIME."


def test_an_empty_iterator_of_certificates_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeEncrypter(iter([]))

    assert str(raised.value) == "At least one certificate is required to encrypt with S/MIME."


@pytest.mark.parametrize(
    ("certificates", "shown"),
    [
        pytest.param(["x\x00y"], "x\\x00y", id="a null byte"),
        pytest.param("file://\x00", "\\x00", id="a null byte after file://"),
    ],
)
def test_a_path_holding_a_null_byte_is_refused(certificates: str | list[str], shown: str) -> None:
    with pytest.raises(MimeRuntimeError) as raised:
        _ = SMimeEncrypter(certificates)

    assert str(raised.value).startswith(f'Unable to read the file "{shown}": ')


def test_a_recipient_whose_key_does_not_load_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "sm2.crt"
    _ = path.write_bytes(unsupported_key_certificate_pem())

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeEncrypter(path)

    assert str(raised.value).startswith(f'Unable to load the key of S/MIME certificate "{path}": ')


def test_a_certificate_file_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    missing = tmp_path / "missing.crt"

    with pytest.raises(MimeRuntimeError) as raised:
        _ = SMimeEncrypter(f"file://{missing}")

    assert str(raised.value) == f'File does not exist: "{missing}".'


def test_the_message_encrypted_is_left_as_it_was(tmp_path: Path) -> None:
    original = email()
    before = wire(original)

    encrypted = encrypter(tmp_path).encrypt(original)
    _ = encrypted.get_headers().add_text_header("X-Added", "after encrypting")

    assert wire(original) == before


def test_the_date_and_message_id_sending_adds_are_the_ones_encrypted(tmp_path: Path) -> None:
    original = Email().from_("noreply@example.com").to("fabien@example.com").text("Hi")

    encrypted = encrypter(tmp_path).encrypt(original)

    sent = wire(encrypted)
    inner = BytesParser(policy=policy.SMTP).parsebytes(decrypt(sent, recipient()))
    outer = BytesParser(policy=policy.SMTP).parsebytes(sent)
    assert outer["Message-ID"] == inner["Message-ID"]
    assert outer["Date"] == inner["Date"]
    assert wire(encrypted) == sent
    assert not original.get_headers().has("Message-ID")


def test_without_the_extra_building_an_encrypter_names_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "cryptography", None)
    monkeypatch.delitem(sys.modules, "xtr_mime.crypto._pkcs7", raising=False)

    with pytest.raises(LogicError) as raised:
        _ = SMimeEncrypter(tmp_path / "encrypt.crt")

    assert str(raised.value) == (
        'The "smime" extra is required to use S/MIME: uv add "xtr-mime[smime]".'
    )
