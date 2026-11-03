"""Messages and their part trees as a queued email carries them: each of its own class."""

from __future__ import annotations

import io
import re

import dkim
import pytest
from xtr_mime import (
    AlternativePart,
    DataPart,
    DigestPart,
    DraftEmail,
    Email,
    FormDataPart,
    Headers,
    Message,
    MessagePart,
    MixedPart,
    RawMessage,
    RelatedPart,
    TextPart,
)
from xtr_mime.crypto import DkimOptions, DkimSigner, SignedBody

from tests.support.dkim_keys import SELECTOR, private_key_pem, published_key
from xtr_mailer import RemoteTemplateEmail
from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.messenger._wire._messages import read_message, write_message

_BOUNDARY = re.compile(rb"(boundary=\"?)[^\";\r\n]+|^--[^\r\n]+", re.MULTILINE)


def _back(message: RawMessage) -> RawMessage:
    return read_message(write_message(message), "message")


def _same(message: RawMessage) -> bytes:
    """The rendered message, boundaries and the made-up Date and Message-ID set aside."""
    rendered = b"".join(message.to_iterable())
    return _BOUNDARY.sub(b"-", re.sub(rb"(?m)^(Date|Message-ID): .*\r\n", b"", rendered))


def _email() -> Email:
    return Email().from_("a@example.com").to("b@example.com").subject("Hi")


def test_a_raw_message_comes_back_as_its_bytes() -> None:
    back = _back(RawMessage(iter([b"Subject: a\r\n", b"\r\nbody"])))

    assert type(back) is RawMessage
    assert back.to_string() == "Subject: a\r\n\r\nbody"


@pytest.mark.parametrize("kind", [Email, DraftEmail, RemoteTemplateEmail])
def test_each_email_comes_back_of_its_class(kind: type[Email]) -> None:
    email = kind().from_("a@example.com").to("b@example.com").text("Hello")

    assert type(_back(email)) is kind


def test_an_email_keeps_its_text_html_charsets_and_attachments() -> None:
    email = (
        Email()
        .from_("a@example.com")
        .to("b@example.com")
        .text(io.BytesIO("Grüße".encode("iso-8859-1")), "iso-8859-1")
        .html("<p>Hi <img src='cid:logo'></p>")
        .attach(b"\x00\x01", "data.bin")
        .embed(b"\x89PNG", "logo", "image/png")
    )
    expected = _same(email)

    back = _back(email)

    assert isinstance(back, Email)
    assert back.get_text_body() == "Grüße".encode("iso-8859-1")
    assert (back.get_text_charset(), back.get_html_charset()) == ("iso-8859-1", "utf-8")
    assert back.get_html_body() == "<p>Hi <img src='cid:logo'></p>"
    assert [a.get_filename() for a in back.get_attachments()] == ["data.bin", "logo"]
    assert _same(back) == expected


def test_an_email_without_a_text_keeps_none() -> None:
    back = _back(Email().html("<p>Hi</p>"))

    assert isinstance(back, Email)
    assert (back.get_text_body(), back.get_text_charset()) == (None, None)


def test_a_remote_template_comes_back_with_its_variables() -> None:
    email = RemoteTemplateEmail().from_("a@example.com").to("b@example.com")
    _ = email.template("welcome", {"firstName": "Fabien", "items": [1, 2.5, None, True]})

    back = _back(email)

    assert isinstance(back, RemoteTemplateEmail)
    template = back.get_remote_template()
    assert template is not None
    assert template.get_reference() == "welcome"
    assert template.get_variables() == {"firstName": "Fabien", "items": [1, 2.5, None, True]}


def test_a_message_keeps_its_body_tree() -> None:
    inner = _email().text("inner")
    body = MixedPart(
        RelatedPart(
            AlternativePart(TextPart("t"), TextPart("<p>h</p>", subtype="html")),
            DataPart(b"i", "i.png", "image/png").as_inline(),
        ),
        MessagePart(inner),
        DigestPart(MessagePart(RawMessage(b"Subject: d\r\n\r\nd"))),
    )
    message = Message(Headers().add_mailbox_list_header("From", ["a@example.com"]), body)

    back = _back(message)

    assert type(back) is Message
    assert _same(back) == _same(message)
    tree = back.get_body()
    assert isinstance(tree, MixedPart)
    assert [type(p) for p in tree.get_parts()] == [RelatedPart, MessagePart, DigestPart]


def test_an_email_keeps_a_body_set_on_it() -> None:
    email = _email().set_body(TextPart("set"))

    back = _back(email)

    assert isinstance(back, Email)
    assert isinstance(Message.get_body(back), TextPart)


def test_a_message_signed_with_dkim_comes_back_byte_for_byte() -> None:
    options = DkimOptions().header_canon("simple").body_canon("simple")
    signer = DkimSigner(private_key_pem(), "example.com", SELECTOR, default_options=options)
    signed = signer.sign(_email().bcc("hidden@example.com").text("Hi").attach(b"x", "x.bin"))

    back = _back(signed)

    sent = b"".join(back.to_iterable())
    assert sent == b"".join(signed.to_iterable())
    assert dkim.verify(sent, dnsfunc=published_key)
    assert isinstance(back, Message)
    body = back.get_body()
    assert isinstance(body, SignedBody)
    assert isinstance(body.get_signed_part(), MixedPart)
    assert back.get_headers().get_header_body("Bcc") is not None


def test_an_email_of_a_class_the_queue_does_not_know_is_refused_when_written() -> None:
    class _Custom(Email):
        pass

    with pytest.raises(InvalidArgumentError, match="_Custom"):
        _ = write_message(_Custom())


def test_a_part_of_a_class_the_queue_does_not_know_is_refused_when_written() -> None:
    message = Message(Headers(), FormDataPart({"a": "b"}))

    with pytest.raises(InvalidArgumentError, match="FormDataPart"):
        _ = write_message(message)


def test_parts_nested_deeper_than_32_are_refused_when_written() -> None:
    part: TextPart | MixedPart = TextPart("x")
    for _ in range(40):
        part = MixedPart(part)

    with pytest.raises(InvalidArgumentError, match="nested"):
        _ = write_message(Message(Headers(), part))


def _written_tree(depth: int) -> dict[str, object]:
    written = write_message(Message(Headers(), TextPart("x")))
    body: object = written["body"]
    for _ in range(depth):
        body = {"$type": "mixed", "headers": {"line_length": 76, "fields": []}, "parts": [body]}
    return {**written, "body": body}


def test_parts_nested_deeper_than_32_are_refused_when_read() -> None:
    with pytest.raises(InvalidArgumentError, match="nested"):
        _ = read_message(_written_tree(40), "message")


def test_parts_nested_32_deep_are_read() -> None:
    assert isinstance(read_message(_written_tree(30), "message"), Message)


@pytest.mark.parametrize(
    "changed",
    [
        {"$type": "x-evil"},
        {"text_charset": 3},
        {"text_charset": {"__str__": "gadget"}},
        {"html_charset": 3},
        {"attachments": [{"$type": "text"}]},
        {"text": {"path": "/etc/passwd"}},
    ],
    ids=["class", "text charset", "charset object", "html charset", "attachment", "path"],
)
def test_an_email_its_fields_refuse_is_refused(changed: dict[str, object]) -> None:
    written = write_message(Email().text("t").html("h"))

    with pytest.raises(InvalidArgumentError) as raised:
        _ = read_message({**written, **changed}, "message")

    assert str(raised.value).startswith("The queued email cannot be read: message")
    assert "passwd" not in str(raised.value)
    assert "gadget" not in str(raised.value)


@pytest.mark.parametrize(
    "template",
    ["welcome", 3, {"reference": 3, "variables": {}}, {"reference": "w", "variables": [1]}],
)
def test_a_template_of_the_wrong_shape_is_refused(template: object) -> None:
    written = write_message(RemoteTemplateEmail().template("welcome"))

    with pytest.raises(InvalidArgumentError, match=r"message\.template"):
        _ = read_message({**written, "template": template}, "message")


def test_an_attachment_that_is_no_data_part_is_refused() -> None:
    written = write_message(Email().attach(b"x"))
    text = write_message(Message(Headers(), TextPart("x")))["body"]

    with pytest.raises(InvalidArgumentError, match=r"message.attachments\[0\]"):
        _ = read_message({**written, "attachments": [text]}, "message")


def test_a_body_without_its_charset_is_refused() -> None:
    written = write_message(Email().text("t"))

    with pytest.raises(InvalidArgumentError, match=r"message\.text_charset is null"):
        _ = read_message({**written, "text_charset": None}, "message")


def test_an_attached_object_that_is_no_message_is_refused_when_written() -> None:
    class _Rendered:
        def to_string(self) -> str:
            return ""

        def to_iterable(self) -> list[bytes]:
            return []

    with pytest.raises(InvalidArgumentError, match="no message"):
        _ = write_message(Message(Headers(), MessagePart(_Rendered())))


def _tree(kind: str, *parts: object) -> dict[str, object]:
    headers: dict[str, object] = {"line_length": 76, "fields": []}
    written = write_message(Message(Headers(), TextPart("x")))
    return {**written, "body": {"$type": kind, "headers": headers, "parts": list(parts)}}


def test_a_digest_of_anything_but_attached_messages_is_refused() -> None:
    text = write_message(Message(Headers(), TextPart("x")))["body"]

    with pytest.raises(InvalidArgumentError, match=r"message\.body is not a multipart"):
        _ = read_message(_tree("digest", text), "message")


def test_a_related_part_of_one_part_is_refused() -> None:
    text = write_message(Message(Headers(), TextPart("x")))["body"]

    with pytest.raises(InvalidArgumentError, match=r"message\.body is not a multipart"):
        _ = read_message(_tree("related", text), "message")
