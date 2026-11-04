"""What an email writes on the wire, and that nothing hostile it is handed gets there as such."""

from __future__ import annotations

from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from typing import TYPE_CHECKING, Final, cast

import pytest

from tests.support.email_cases import GIF, addressed_email, assert_clean_error, decoded
from xtr_mime import Email
from xtr_mime.exception import InvalidArgumentError, LogicError, MimeError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def test_to_string_renders_text_html_an_attachment_and_an_inline_image() -> None:
    email = addressed_email().subject("Hello").text("text content")
    _ = email.html('<p>html</p><img src="cid:logo.gif">').embed(
        GIF.read_bytes(), "logo.gif", "image/gif"
    )
    _ = email.attach(b"report", "report.txt", "text/plain")

    parsed = BytesParser(policy=policy.default).parsebytes(b"".join(email.to_iterable()))

    assert parsed["Subject"] == "Hello"
    assert [part.get_content_type() for part in parsed.walk()] == [
        "multipart/mixed",
        "multipart/related",
        "multipart/alternative",
        "text/plain",
        "text/html",
        "image/gif",
        "text/plain",
    ]
    image = next(part for part in parsed.walk() if part.get_content_type() == "image/gif")
    html = next(part for part in parsed.walk() if part.get_content_type() == "text/html")
    content_id = str(cast("object", image["Content-ID"])).strip("<>")
    assert f'src="cid:{content_id}"'.encode() in decoded(html)
    assert decoded(image) == GIF.read_bytes()


# Hostile input: whatever a setter is handed, a message is either refused with one of this
# package's errors, its text free of what was handed raw, or written without a header of its own.

INJECTED: Final = "x@example.com\r\nBcc: victim@example.com"


def _render_or_refuse(email: Email) -> bytes | None:
    """Render ``email``; return ``None`` when it is refused, checking the error is clean."""
    try:
        return b"".join(email.to_iterable())
    except MimeError as error:
        assert_clean_error(error)
        return None


def _headers_of(rendered: bytes) -> list[str]:
    head = rendered.partition(b"\r\n\r\n")[0].decode("utf-8", "surrogateescape")
    return [
        line.partition(":")[0] for line in head.split("\r\n") if not line.startswith((" ", "\t"))
    ]


def _addresses_of(rendered: bytes) -> list[str]:
    """Return every address a reader finds in the address headers of ``rendered``."""
    parsed = BytesParser(policy=policy.default).parsebytes(rendered)
    names = ("From", "Sender", "Reply-To", "To", "Cc", "Bcc", "Return-Path")
    values = [str(cast("object", parsed[name])) for name in names if name in parsed]
    return [address for _, address in getaddresses(values)]


HOSTILE_VALUES: Final[list[tuple[str, Callable[[Email], Email]]]] = [
    ("subject-crlf", lambda email: email.subject("Hi\r\nBcc: victim@example.com")),
    ("subject-lf", lambda email: email.subject("Hi\nBcc: victim@example.com")),
    ("subject-nul", lambda email: email.subject("Hi\x00there")),
    ("subject-surrogate", lambda email: email.subject("Hi \udce9")),
    ("subject-encoded-crlf", lambda email: email.subject("=?utf-8?q?=0D=0ABcc:_v@example.com?=")),
    ("subject-overlong-word", lambda email: email.subject("x" * 1000)),
    ("attach-name", lambda email: email.attach(b"x", "evil\r\nBcc: victim@example.com.txt")),
    (
        "attach-content-type",
        lambda email: email.attach(b"x", "evil.txt", "text/plain\r\nBcc: victim@example.com"),
    ),
    ("embed-name-nul", lambda email: email.embed(b"x", "evil\x00.gif")),
    ("attach-name-surrogate", lambda email: email.attach(b"x", "evil\udce9.txt")),
    ("text-surrogate", lambda email: email.text("caf\udce9")),
    ("html-surrogate", lambda email: email.html("caf\udce9")),
    ("text-charset", lambda email: email.text("text", "utf-8\r\nBcc: victim@example.com")),
    ("text-unknown-charset", lambda email: email.text("text", "no-such-charset")),
]


@pytest.mark.parametrize(
    "build", [build for _, build in HOSTILE_VALUES], ids=[label for label, _ in HOSTILE_VALUES]
)
def test_a_hostile_value_never_reaches_the_wire_as_a_header(
    build: Callable[[Email], Email],
) -> None:
    email = build(addressed_email().text("body"))

    rendered = _render_or_refuse(email)

    if rendered is not None:
        assert "Bcc" not in _headers_of(rendered)
        assert all(len(line) <= 998 for line in rendered.split(b"\r\n"))


ADDRESS_SETTERS: Final[list[tuple[str, Callable[[Email, str], Email]]]] = [
    ("from", lambda email, value: email.from_(value)),
    ("add_from", lambda email, value: email.add_from(value)),
    ("reply_to", lambda email, value: email.reply_to(value)),
    ("add_reply_to", lambda email, value: email.add_reply_to(value)),
    ("to", lambda email, value: email.to(value)),
    ("add_to", lambda email, value: email.add_to(value)),
    ("cc", lambda email, value: email.cc(value)),
    ("add_cc", lambda email, value: email.add_cc(value)),
    ("bcc", lambda email, value: email.bcc(value)),
    ("add_bcc", lambda email, value: email.add_bcc(value)),
    ("sender", lambda email, value: email.sender(value)),
    ("return_path", lambda email, value: email.return_path(value)),
]

HOSTILE_ADDRESSES: Final = [
    INJECTED,
    "x@example.com\nBcc: victim@example.com",
    "x@exa\x00mple.com",
    "x\udce9@example.com",
    "Name\r\nBcc: victim@example.com <x@example.com>",
    "=?utf-8?q?victim@example.com?= <x@example.com>",
    "x@" + "a" * 2000 + ".com",
]


@pytest.mark.parametrize(
    "set_address",
    [set_address for _, set_address in ADDRESS_SETTERS],
    ids=[label for label, _ in ADDRESS_SETTERS],
)
@pytest.mark.parametrize("value", HOSTILE_ADDRESSES, ids=range(len(HOSTILE_ADDRESSES)))
def test_a_hostile_address_never_adds_a_recipient(
    set_address: Callable[[Email, str], Email], value: str
) -> None:
    email = Email().from_("me@example.com").to("you@example.com").text("body")
    try:
        _ = set_address(email, value)
    except (InvalidArgumentError, LogicError) as error:
        assert_clean_error(error)
        return

    rendered = _render_or_refuse(email)

    if rendered is not None:
        assert "Bcc" not in _headers_of(rendered)
        assert "victim@example.com" not in _addresses_of(rendered)


def test_a_hostile_path_is_refused_without_its_raw_value() -> None:
    email = (
        addressed_email()
        .text("body")
        .attach_from_path("/no/such\r\nBcc: victim@example.com\x00.txt")
    )

    with pytest.raises(InvalidArgumentError) as caught:
        _ = email.to_string()

    assert_clean_error(caught.value)


def test_a_long_line_of_body_text_is_folded_for_the_wire() -> None:
    email = addressed_email().text("word " * 4000).html("<p>" + "x" * 20000 + "</p>")

    rendered = b"".join(email.to_iterable())

    assert max(len(line) for line in rendered.split(b"\r\n")) <= 78
    parsed = BytesParser(policy=policy.default).parsebytes(rendered)
    html = next(part for part in parsed.walk() if part.get_content_type() == "text/html")
    assert decoded(html).rstrip(b"\r\n") == b"<p>" + b"x" * 20000 + b"</p>"


def test_a_huge_attachment_from_a_path_is_yielded_in_several_chunks(tmp_path: Path) -> None:
    # The email is rendered whole before the first chunk (see the README's Known limitations):
    # this checks only that it comes in several chunks that put back together hold the file.
    path = tmp_path / "huge.bin"
    data = bytes(range(256)) * (4 * 1024 * 4)  # 4 MiB
    _ = path.write_bytes(data)
    email = addressed_email().text("body").attach_from_path(path)

    chunks = list(email.to_iterable())

    assert len(chunks) > 1
    parsed = BytesParser(policy=policy.default).parsebytes(b"".join(chunks))
    attachment = next(part for part in parsed.walk() if part.get_filename() == "huge.bin")
    assert decoded(attachment) == data
