"""An S/MIME signer turns a message's body into a signed multipart a verifier accepts.

Every signature is checked by hand with cryptography against the run's CA (see
:mod:`tests.support.smime_checks`), and once more with ``openssl smime -verify`` where an
openssl binary is installed. Upstream's serialization case becomes the message rendered again
and again: a part is not serialized here, a signed message sends the same bytes every time.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from xtr_clock import MockClock

from tests.support.smime_extra import require_smime_extra

require_smime_extra()

# Imported after the skip: without the extra these modules do not import.
from tests.support.smime_certificates import (  # noqa: E402 -- see above.
    authority,
    chained_signer,
    ec_signer,
    intermediate,
)
from tests.support.smime_checks import (  # noqa: E402 -- see above.
    openssl_verifies,
    signed_parts,
    verifies,
    wire,
)
from tests.support.smime_signing import (  # noqa: E402 -- see above.
    assert_signature_holds,
    email,
    encrypter,
    message,
    signer,
)
from xtr_mime import (  # noqa: E402 -- see above.
    Address,
    DataPart,
    Email,
    Headers,
    Message,
    TextPart,
)
from xtr_mime.crypto import SMimeSigner  # noqa: E402 -- see above.

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "mimetypes"


def test_a_signed_message_verifies(tmp_path: Path) -> None:
    original = message()

    signed = signer(tmp_path).sign(original)

    assert_signature_holds(signed, original)


def test_an_encrypted_message_signed_verifies(tmp_path: Path) -> None:
    original = email()
    encrypted = encrypter(tmp_path).encrypt(original)

    signed = signer(tmp_path).sign(encrypted)

    assert_signature_holds(signed, original)


@pytest.mark.parametrize("passphrase", ["xtr-rocks", os.fsdecode(b"p\xe4sswort-geheim")])
def test_a_passphrase_protected_key_signs(tmp_path: Path, passphrase: str) -> None:
    original = message()

    signed = signer(tmp_path, passphrase=passphrase).sign(original)

    assert_signature_holds(signed, original)


def test_every_rendering_of_a_signed_message_is_the_same_and_verifies(tmp_path: Path) -> None:
    original = email()
    signed = signer(tmp_path).sign(original)

    renderings = {wire(signed), signed.to_string().encode(), wire(signed)}

    assert len(renderings) == 1
    assert_signature_holds(signed, original)


def test_a_signed_message_keeps_bcc_without_writing_it(tmp_path: Path) -> None:
    original = email().add_bcc("fabien@example.com", "s.stok@example.net")
    _ = original.subject("I am your sign of fear")

    signed = signer(tmp_path).sign(original)

    assert_signature_holds(signed, original)


def test_a_message_with_attachments_verifies(tmp_path: Path) -> None:
    headers = Headers().add_mailbox_list_header("From", ["fabien@example.com"])
    original = Email(headers.add_mailbox_list_header("To", ["fabien@example.com"]))
    _ = original.html('html content <img src="cid:test.gif">').text("text content")
    with (
        (_FIXTURES / "test").open("rb") as data,
        (_FIXTURES / "test.gif").open("rb") as gif,
    ):
        _ = original.add_part(DataPart(data)).add_part(DataPart(gif, "test.gif"))

        signed = signer(tmp_path).sign(original)

    assert_signature_holds(signed, original)


def test_extra_certificates_complete_the_chain(tmp_path: Path) -> None:
    certificate, key = chained_signer().write(tmp_path, "chained")
    extra = intermediate().write(tmp_path, "intermediate")[0]
    original = message()

    signed = SMimeSigner(certificate, key, extra_certificates=extra).sign(original)
    bare = SMimeSigner(certificate, key).sign(original)

    assert_signature_holds(signed, original)
    assert not verifies(wire(bare), authority().certificate)


def test_a_message_with_non_ascii_headers_and_an_attachment_verifies(tmp_path: Path) -> None:
    original = (
        email()
        .from_(Address("fabien@example.com", "Fabién Pötencier"))
        .subject("Grüße — ça va?")
        .attach("ünïcödé ✓".encode(), "naïve.txt", "text/plain")
    )

    signed = signer(tmp_path).sign(original)

    assert_signature_holds(signed, original)


def test_an_elliptic_curve_key_signs(tmp_path: Path) -> None:
    original = message()

    signed = signer(tmp_path, ec_signer()).sign(original)

    assert_signature_holds(signed, original)


@pytest.mark.parametrize(
    ("algorithm", "micalg"),
    [("sha224", "sha-224"), ("sha256", "sha-256"), ("sha384", "sha-384"), ("sha512", "sha-512")],
)
def test_the_algorithm_asked_for_signs(tmp_path: Path, algorithm: str, micalg: str) -> None:
    certificate, key = ec_signer().write(tmp_path, "sign")
    original = message()

    signed = SMimeSigner(certificate, key, algorithm=algorithm).sign(original)

    body = signed.get_body()
    assert body is not None
    assert body.get_prepared_headers().get_header_parameter("Content-Type", "micalg") == micalg
    assert_signature_holds(signed, original)


def test_the_body_is_signed_as_it_renders_and_the_headers_are_the_message_s_as_sent(
    tmp_path: Path,
) -> None:
    original = message("Hello")

    signed = signer(tmp_path).sign(original)

    body = signed.get_body()
    assert body is not None
    assert (body.get_media_type(), body.get_media_subtype()) == ("multipart", "signed")
    assert signed_parts(wire(signed))[0] == b"".join(TextPart("Hello").to_iterable())
    assert signed.get_headers().get_names() == [*original.get_headers().get_names(), "message-id"]


def _clocked_email() -> Email:
    clock = MockClock(datetime(2020, 1, 1, 10, tzinfo=UTC))
    return Email(clock=clock).from_("a@example.com").to("b@example.com").text("x")


def test_a_signed_message_is_dated_by_the_clock_of_the_message_signed(tmp_path: Path) -> None:
    original = _clocked_email()
    _ = original.get_headers().add_id_header("Message-ID", "some@id")

    signed = signer(tmp_path).sign(original)

    assert b"\r\nDate: Wed, 01 Jan 2020 10:00:00 +0000\r\n" in wire(signed)


def test_a_signed_message_without_a_date_or_message_id_renders_the_same_every_time(
    tmp_path: Path,
) -> None:
    signed = signer(tmp_path).sign(_clocked_email())

    assert len({wire(signed), wire(signed), signed.to_string().encode()}) == 1


def test_a_message_without_a_body_is_signed_with_an_empty_text(tmp_path: Path) -> None:
    original = Message(Headers().add_mailbox_list_header("From", ["fabien@example.com"]))

    signed = signer(tmp_path).sign(original)

    assert signed_parts(wire(signed))[0] == b"".join(TextPart("").to_iterable())
    assert verifies(wire(signed), authority().certificate)


def test_the_message_signed_is_left_as_it_was(tmp_path: Path) -> None:
    original = message()
    before = original.get_headers().to_string()

    signed = signer(tmp_path).sign(original)
    _ = signed.get_headers().add_text_header("X-Added", "after signing")

    assert original.get_headers().to_string() == before
    assert isinstance(original.get_body(), TextPart)


def test_openssl_verifies_a_signed_message_where_it_is_installed(tmp_path: Path) -> None:
    signed = wire(signer(tmp_path).sign(email()))

    verified = openssl_verifies(signed, authority().certificate, tmp_path)

    if verified is None:
        pytest.skip("no openssl binary installed")
    assert verified
