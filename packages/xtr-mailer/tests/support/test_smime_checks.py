"""The S/MIME checks accept what cryptography signs and refuse what does not hold.

The listener tests trust :func:`verifies`; here it is checked against signatures cryptography
makes on its own, unchanged and changed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7

from tests.support.smime_checks import decrypt, openssl_verifies, signed_parts, verifies
from tests.support.smime_identities import authority, identity

if TYPE_CHECKING:
    from pathlib import Path

_CONTENT = b"Content-Type: text/plain\r\n\r\nsigned\r\n"


def _signed() -> bytes:
    signer = identity("signer@example.com")
    return (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(_CONTENT)
        .add_signer(signer.certificate, signer.private_key, hashes.SHA256())
        .sign(
            serialization.Encoding.SMIME,
            [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
        )
    )


def test_a_signature_cryptography_makes_verifies() -> None:
    assert verifies(_signed(), authority().certificate)


def test_the_signed_part_is_cut_as_sent() -> None:
    assert signed_parts(_signed())[0] == _CONTENT


def test_a_changed_signed_part_does_not_verify() -> None:
    sent = _signed().replace(b"signed\r\n", b"signed!\r\n", 1)

    assert not verifies(sent, authority().certificate)


def test_a_signer_the_trusted_ca_did_not_issue_does_not_verify() -> None:
    assert not verifies(_signed(), identity("r1@example.com").certificate)


def test_a_message_that_is_not_signed_does_not_verify() -> None:
    assert not verifies(b"Content-Type: text/plain\r\n\r\nhi\r\n", authority().certificate)


def test_openssl_agrees_where_it_is_installed(tmp_path: Path) -> None:
    good = openssl_verifies(_signed(), authority().certificate, tmp_path)
    if good is None:
        pytest.skip("no openssl binary installed")
    sent = _signed().replace(b"signed\r\n", b"signed!\r\n", 1)

    assert good
    assert openssl_verifies(sent, authority().certificate, tmp_path) is False


def test_an_encrypted_message_decrypts_to_its_content() -> None:
    reader = identity("r1@example.com")
    encrypted = (
        pkcs7.PKCS7EnvelopeBuilder()
        .set_data(_CONTENT)
        .add_recipient(reader.certificate)
        .encrypt(serialization.Encoding.SMIME, [pkcs7.PKCS7Options.Binary])
    )

    assert decrypt(encrypted, reader) == _CONTENT


def test_an_identity_is_written_with_its_key_encrypted_when_given_a_passphrase(
    tmp_path: Path,
) -> None:
    certificate, key = identity("r1@example.com").write(tmp_path, "r1", "secret")

    assert certificate.read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")
    assert key.read_bytes().startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----")
