"""An S/MIME part: a body already encoded, written under the media type and parameters given.

Upstream's cases are all about unserializing a part from untrusted data, which has no
counterpart: a part is not serialized. These cover what the part renders instead.
"""

from __future__ import annotations

from xtr_mime import Message
from xtr_mime.header import Headers
from xtr_mime.part import SMimePart

_SIGNED_BODY = (
    b"This is an S/MIME signed message\r\n"
    b"\r\n"
    b"--b0undary\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    b"Content-Transfer-Encoding: quoted-printable\r\n"
    b"\r\n"
    b"content  \r\n"
    b"--b0undary\r\n"
    b'Content-Type: application/x-pkcs7-signature; name="smime.p7s"\r\n'
    b"Content-Transfer-Encoding: base64\r\n"
    b"\r\n"
    b"c2lnbmF0dXJl\r\n"
    b"--b0undary--\r\n"
)


def _signed() -> SMimePart:
    return SMimePart(
        _SIGNED_BODY,
        "multipart",
        "signed",
        {"protocol": "application/x-pkcs7-signature", "micalg": "sha-256", "boundary": "b0undary"},
    )


def test_the_media_type_is_the_one_given() -> None:
    part = SMimePart("body content", "application", "pkcs7-mime", {})

    assert (part.get_media_type(), part.get_media_subtype()) == ("application", "pkcs7-mime")


def test_the_parameters_are_set_on_content_type() -> None:
    headers = _signed().get_prepared_headers()

    assert headers.get_header_body("Content-Type") == "multipart/signed"
    assert headers.get_header_parameter("Content-Type", "micalg") == "sha-256"
    assert headers.get_header_parameter("Content-Type", "boundary") == "b0undary"


def test_the_prepared_headers_are_a_copy() -> None:
    part = _signed()

    part.get_prepared_headers().remove("Content-Type")

    assert not part.get_headers().has("Content-Type")
    assert part.get_prepared_headers().has("Content-Type")


def test_the_body_is_written_byte_for_byte() -> None:
    assert _signed().body_to_string().encode() == _SIGNED_BODY


def test_the_part_renders_its_headers_then_its_body() -> None:
    rendered = b"".join(_signed().to_iterable())

    head, _, body = rendered.partition(b"\r\n\r\n")
    assert body == _SIGNED_BODY
    assert head.startswith(b"Content-Type: multipart/signed;")


def test_a_header_of_the_caller_s_is_written_too() -> None:
    part = SMimePart("Ym9keQ==\r\n", "application", "pkcs7-mime", {"smime-type": "enveloped-data"})
    _ = part.get_headers().add_text_header("Content-Transfer-Encoding", "base64")

    rendered = part.to_string()

    assert "Content-Transfer-Encoding: base64\r\n" in rendered
    assert rendered.endswith("\r\n\r\nYm9keQ==\r\n")


def test_a_body_with_bare_line_feeds_is_written_with_crlf() -> None:
    part = SMimePart(b"Ym9k\neQ==\n", "application", "pkcs7-mime", {})

    assert part.body_to_string() == "Ym9k\r\neQ==\r\n"


def test_a_signed_body_the_engine_would_rewrite_is_sent_as_given() -> None:
    body = (
        b"x\r\n--b0undary  \r\nSubject:x\r\nX-A:   v\r\nX-C: a\rb\r\n\r\n"
        b"\xe9\xff\r\n--b0undary--\r\n"
    )
    part = SMimePart(body, "multipart", "signed", {"boundary": "b0undary"})
    message = Message(Headers().add_mailbox_list_header("From", ["a@example.com"]), part)

    sent = [b"".join(message.to_iterable()), message.to_string().encode("utf-8", "surrogateescape")]

    assert all(rendered.endswith(b"\r\n\r\n" + body) for rendered in sent)


def test_a_message_with_the_part_as_body_sends_the_body_unchanged() -> None:
    message = Message(Headers().add_mailbox_list_header("From", ["a@example.com"]), _signed())

    sent = b"".join(message.to_iterable())

    assert sent.endswith(b"\r\n\r\n" + _SIGNED_BODY)
    assert sent.count(b"MIME-Version") == 1
