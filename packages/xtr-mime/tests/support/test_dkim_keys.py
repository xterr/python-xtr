"""The test keys publish their public half under one selector, and verify what they signed."""

from __future__ import annotations

from tests.support.dkim_extra import require_dkim_extra

require_dkim_extra()

# Imported after the skip: without the extra these modules do not import.
import dkim  # noqa: E402 -- see above.

from tests.support.dkim_keys import (  # noqa: E402 -- see above.
    DOMAIN,
    SELECTOR,
    dkim_key,
    other_dkim_key,
)

_MESSAGE = b"From: a@testdkim.example.net\r\nTo: b@example.com\r\nSubject: Hi\r\n\r\nBody\r\n"


def _signed(pem: str) -> bytes:
    signature = dkim.DKIM(_MESSAGE).sign(
        SELECTOR.encode(), DOMAIN.encode(), pem.encode(), include_headers=[b"from", b"subject"]
    )
    return signature + _MESSAGE


def test_the_record_is_answered_for_the_selector_only() -> None:
    key = dkim_key()

    assert (key.resolve(b"sf._domainkey.testdkim.example.net.") or b"").startswith(
        b"v=DKIM1; k=rsa; p="
    )
    assert key.resolve(b"other._domainkey.testdkim.example.net.") is None


def test_a_message_signed_with_the_key_verifies() -> None:
    assert dkim_key().verifies(_signed(dkim_key().traditional_pem()))


def test_a_message_signed_with_another_key_does_not_verify() -> None:
    assert not dkim_key().verifies(_signed(other_dkim_key().traditional_pem()))


def test_the_pem_is_encrypted_only_with_a_passphrase() -> None:
    assert "ENCRYPTED" in dkim_key().pem("secret")
    assert "ENCRYPTED" not in dkim_key().pem()
