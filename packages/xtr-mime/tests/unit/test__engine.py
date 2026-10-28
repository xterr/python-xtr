"""Characterisation of the stdlib ``email`` behaviours the rendering engine relies on.

xtr-mime hands all wire work to Python's ``email`` package. Every behaviour that choice depends
on is pinned here, so a change in a new Python release fails in this file first.
"""

from __future__ import annotations

import base64
import quopri
from datetime import UTC, datetime
from email import policy as stdlib_policy
from email.headerregistry import Address, AddressHeader
from email.message import EmailMessage
from email.parser import HeaderParser
from typing import TYPE_CHECKING, cast

import pytest

from xtr_mime import _engine
from xtr_mime._engine import (
    BinaryLeaf,
    Mailbox,
    MailboxGroup,
    Parameterized,
    TextLeaf,
)
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError

if TYPE_CHECKING:
    from xtr_mime._engine import TransferEncoding

LONG_SUBJECT = "Žluťoučký kůň úpěl ďábelské ódy, " * 5


def _decode(field: str) -> str:
    """Read one rendered header field back the way a mail client would."""
    name = field.split(":", 1)[0]
    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    return cast("str", parsed[name])


def _lines(field: str) -> list[str]:
    return field.split("\r\n")


def _text(  # noqa: PLR0913 -- a test builder: every field a test may vary is a keyword
    content: str = "Hello",
    *,
    subtype: str = "plain",
    charset: str = "utf-8",
    transfer_encoding: TransferEncoding = "quoted-printable",
    parameters: dict[str, str] | None = None,
    disposition: Parameterized | None = None,
) -> TextLeaf:
    return TextLeaf(
        content=content,
        subtype=subtype,
        charset=charset,
        transfer_encoding=transfer_encoding,
        parameters=parameters or {},
        disposition=disposition,
    )


def test_the_policy_writes_crlf_and_folds_at_76_columns() -> None:
    assert _engine.POLICY.linesep == "\r\n"
    assert _engine.POLICY.max_line_length == 76
    assert _engine.POLICY.mangle_from_ is False


def test_a_non_ascii_unstructured_header_is_an_encoded_word_that_decodes_back() -> None:
    field = _engine.fold_header("Subject", "Héllo wörld")

    assert "=?utf-8?" in field.lower()
    assert field.isascii()
    assert _decode(field) == "Héllo wörld"


def test_an_ascii_unstructured_header_is_written_as_is() -> None:
    assert _engine.fold_header("X-Mailer", "plain value") == "X-Mailer: plain value"


def test_a_long_header_folds_into_crlf_lines_of_at_most_76_characters() -> None:
    field = _engine.fold_header("Subject", LONG_SUBJECT)

    lines = _lines(field)
    assert len(lines) > 1
    assert all(len(line) <= 76 for line in lines)
    assert all(line.startswith(" ") for line in lines[1:])
    assert "\n" not in field.replace("\r\n", "")
    assert _decode(field) == LONG_SUBJECT


def test_an_unbreakable_ascii_word_still_folds_within_76_characters() -> None:
    word = "x" * 120

    field = _engine.fold_header("X-Long", word)

    assert all(len(line) <= 76 for line in _lines(field))
    assert _decode(field) == word


def test_a_line_break_in_a_value_cannot_start_a_new_field() -> None:
    field = _engine.fold_header("Subject", "Hi\r\nBcc: victim@example.com")

    assert not any(line.startswith("Bcc:") for line in _lines(field))


def test_the_header_body_is_the_folded_field_without_its_name() -> None:
    assert _engine.header_body("Subject", "plain value") == "plain value"
    assert _engine.header_body("X-Empty", "") == ""

    body = _engine.header_body("Subject", LONG_SUBJECT)
    assert "\r\n " in body
    assert _decode("Subject: " + body) == LONG_SUBJECT


def test_a_body_folded_before_its_first_word_loses_the_leading_fold() -> None:
    body = _engine.header_body("From", [Mailbox("Žluťoučký Kůň " * 3, "alice@example.com")])

    assert not body.startswith(("\r\n", " "))


def test_an_address_with_a_non_ascii_display_name_round_trips() -> None:
    field = _engine.fold_header("From", [Mailbox("Žluťoučký Kůň", "alice@example.com")])

    assert field.isascii()
    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    header = cast("AddressHeader", parsed["From"])
    assert [(a.display_name, a.addr_spec) for a in header.addresses] == [
        ("Žluťoučký Kůň", "alice@example.com"),
    ]


def test_an_address_without_a_display_name_is_written_bare() -> None:
    assert _engine.header_body("To", [Mailbox("", "bob@example.com")]) == "bob@example.com"


def test_a_quoted_local_part_keeps_its_quotes() -> None:
    body = _engine.header_body("To", [Mailbox("", '"john doe"@example.com')])

    assert body == '"john doe"@example.com'


def test_an_address_list_with_groups_round_trips() -> None:
    value = [
        MailboxGroup("Ündisclosed", (Mailbox("Bob", "bob@example.com"),)),
        Mailbox("Carol", "carol@example.com"),
        MailboxGroup("nobody", ()),
    ]

    field = _engine.fold_header("To", value)

    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    groups = cast("AddressHeader", parsed["To"]).groups
    assert [(g.display_name, [a.addr_spec for a in g.addresses]) for g in groups] == [
        ("Ündisclosed", ["bob@example.com"]),
        (None, ["carol@example.com"]),
        ("nobody", []),
    ]


def test_a_date_header_is_written_in_rfc_5322_form() -> None:
    moment = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)

    assert _engine.header_body("Date", moment) == "Tue, 02 Jan 2024 03:04:05 +0000"


def test_a_non_ascii_parameter_is_rfc_2231_encoded_and_decodes_back() -> None:
    value = Parameterized("attachment", {"filename": 'résumé "final".pdf'})

    field = _engine.fold_header("Content-Disposition", value)

    assert field.isascii()
    assert "filename*=" in field
    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    assert parsed.get_filename() == 'résumé "final".pdf'
    assert parsed.get_content_disposition() == "attachment"


def test_a_content_type_keeps_its_parameters() -> None:
    field = _engine.fold_header(
        "Content-Type", Parameterized("text/plain", {"charset": "utf-8", "name": "a.txt"})
    )

    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    assert parsed.get_content_type() == "text/plain"
    assert parsed.get_param("charset") == "utf-8"
    assert parsed.get_param("name") == "a.txt"


def test_the_bare_engine_still_mangles_a_unicode_domain_gh_83938_canary() -> None:
    """CPython gh-83938: the engine writes a raw Unicode domain as an encoded word.

    When this starts failing the engine renders the domain correctly by itself and the
    punycoding in ``encode_idn_address`` (and its call in the address rendering) can go.
    """
    message = EmailMessage(policy=_engine.POLICY)
    message["From"] = Address("Alice", addr_spec="alice@dømi.fo")

    field = message.as_bytes().split(b"\r\n\r\n", 1)[0].decode("ascii")

    assert "alice@=?utf-8?" in field.lower()


def test_a_unicode_domain_is_punycoded_before_the_engine_sees_it() -> None:
    assert _engine.encode_idn_address("alice@dømi.fo") == "alice@xn--dmi-0na.fo"


def test_an_address_header_with_a_unicode_domain_is_written_correctly() -> None:
    body = _engine.header_body("From", [Mailbox("Žluťoučký Kůň", "alice@dømi.fo")])

    assert body.endswith("<alice@xn--dmi-0na.fo>")


@pytest.mark.parametrize(
    "address",
    ["alice@Example.COM", "alice@[192.0.2.1]", "no-domain", "Žluť@example.com"],
)
def test_an_ascii_domain_is_left_untouched(address: str) -> None:
    assert _engine.encode_idn_address(address) == address


@pytest.mark.parametrize("domain", ["a_b.dø", "-x.dø", "xn--zz.dø"])
def test_a_domain_idna_refuses_is_an_rfc_compliance_error(domain: str) -> None:
    with pytest.raises(RfcComplianceError, match=domain):
        _ = _engine.encode_idn_address(f"alice@{domain}")


@pytest.mark.parametrize("address", ["no-domain", "a@b@c", "@example.com", "a b@example.com"])
def test_an_address_the_engine_cannot_parse_is_an_rfc_compliance_error(address: str) -> None:
    with pytest.raises(RfcComplianceError, match="email address"):
        _ = _engine.fold_header("To", [Mailbox("", address)])


def test_a_line_break_in_a_display_name_is_an_rfc_compliance_error() -> None:
    with pytest.raises(RfcComplianceError):
        _ = _engine.fold_header("To", [Mailbox("a\r\nBcc: x", "bob@example.com")])


@pytest.mark.parametrize("encoding", ["quoted-printable", "base64", "8bit", "7bit"])
def test_a_text_leaf_honours_the_requested_transfer_encoding(encoding: TransferEncoding) -> None:
    content = "Hello" if encoding == "7bit" else "Héllo wörld"

    part = _engine.build_text(_text(content, transfer_encoding=encoding))

    assert part["Content-Transfer-Encoding"] == encoding
    # Inside base64 the engine encodes CRLF line ends, which decoding keeps.
    assert part.get_content() == content + ("\r\n" if encoding == "base64" else "\n")


def test_a_text_leaf_body_is_encoded_on_the_wire() -> None:
    raw = _engine.to_bytes(_engine.build_text(_text("Héllo", transfer_encoding="base64")))
    qp = _engine.to_bytes(_engine.build_text(_text("Héllo")))
    eight = _engine.to_bytes(_engine.build_text(_text("Héllo", transfer_encoding="8bit")))

    assert base64.b64decode(raw.split(b"\r\n\r\n", 1)[1]) == b"H\xc3\xa9llo\r\n"
    assert quopri.decodestring(qp.split(b"\r\n\r\n", 1)[1]) == b"H\xc3\xa9llo\r\n"
    assert eight.split(b"\r\n\r\n", 1)[1] == b"H\xc3\xa9llo\r\n"


def test_a_text_leaf_always_ends_with_a_line_break() -> None:
    part = _engine.build_text(_text("no newline"))

    assert part.get_content() == "no newline\n"


def test_a_text_leaf_carries_its_charset_and_extra_parameters() -> None:
    part = _engine.build_text(
        _text("Ahoj", subtype="html", charset="iso-8859-2", parameters={"name": "ahoj.html"})
    )

    assert part.get_content_type() == "text/html"
    assert part.get_param("charset") == "iso-8859-2"
    assert part.get_param("name") == "ahoj.html"
    assert list(part.keys())[:2] == ["Content-Type", "Content-Transfer-Encoding"]


def test_a_text_leaf_in_a_charset_python_does_not_know_is_an_invalid_argument() -> None:
    with pytest.raises(InvalidArgumentError, match="no-such-charset"):
        _ = _engine.build_text(_text(charset="no-such-charset"))


def test_a_text_leaf_its_charset_cannot_hold_is_an_invalid_argument() -> None:
    with pytest.raises(InvalidArgumentError, match="us-ascii"):
        _ = _engine.build_text(_text("Žluť", charset="us-ascii"))


def test_a_seven_bit_text_leaf_with_non_ascii_content_is_an_invalid_argument() -> None:
    with pytest.raises(InvalidArgumentError, match="7bit"):
        _ = _engine.build_text(_text("Žluť", transfer_encoding="7bit"))


def test_a_text_leaf_can_be_an_attachment() -> None:
    part = _engine.build_text(_text(disposition=Parameterized("attachment", {"name": "hello.txt"})))

    assert part.get_content_disposition() == "attachment"
    assert part.get_param("name", header="Content-Disposition") == "hello.txt"


def test_a_binary_leaf_keeps_an_inline_disposition_and_its_content_id() -> None:
    part = _engine.build_binary(
        BinaryLeaf(
            content=b"\x89PNG\x00\xff",
            maintype="image",
            subtype="png",
            transfer_encoding="base64",
            disposition=Parameterized("inline", {"filename": "logo.png"}),
            content_id="<logo@xtr>",
        )
    )

    assert part.get_content_type() == "image/png"
    assert part.get_content_disposition() == "inline"
    assert part.get_filename() == "logo.png"
    assert part["Content-ID"] == "<logo@xtr>"
    assert part.get_content() == b"\x89PNG\x00\xff"


@pytest.mark.parametrize("encoding", ["quoted-printable", "base64", "8bit"])
def test_a_binary_leaf_honours_the_requested_transfer_encoding(encoding: TransferEncoding) -> None:
    part = _engine.build_binary(
        BinaryLeaf(
            content=b"plain bytes",
            maintype="application",
            subtype="x-thing",
            transfer_encoding=encoding,
            parameters={"name": "thing.bin"},
        )
    )

    assert part["Content-Transfer-Encoding"] == encoding
    assert part.get_param("name") == "thing.bin"
    assert part.get_content() == b"plain bytes"


def test_a_text_typed_binary_leaf_carries_no_charset() -> None:
    part = _engine.build_binary(
        BinaryLeaf(content=b"raw", maintype="text", subtype="plain", transfer_encoding="base64")
    )

    assert part.get_content_type() == "text/plain"
    assert part.get_param("charset") is None
    assert part["Content-Transfer-Encoding"] == "base64"


def test_a_seven_bit_binary_leaf_with_eight_bit_bytes_is_an_invalid_argument() -> None:
    leaf = BinaryLeaf(
        content=b"\xff", maintype="application", subtype="x", transfer_encoding="7bit"
    )

    with pytest.raises(InvalidArgumentError, match="7bit"):
        _ = _engine.build_binary(leaf)


def test_the_engine_content_setter_adds_a_mime_version() -> None:
    message = EmailMessage(policy=_engine.POLICY)
    message.set_content("x")

    assert message["MIME-Version"] == "1.0"


def test_a_leaf_drops_the_mime_version_the_setter_added() -> None:
    assert _engine.build_text(_text())["MIME-Version"] is None
    binary = _engine.build_binary(
        BinaryLeaf(content=b"x", maintype="application", subtype="x", transfer_encoding="base64")
    )
    assert binary["MIME-Version"] is None


def test_a_multipart_uses_the_supplied_boundary_and_strips_sub_part_mime_versions() -> None:
    parsed_child = _engine.parse(b"MIME-Version: 1.0\r\nContent-Type: text/plain\r\n\r\nhi\r\n")

    multipart = _engine.build_multipart(
        "mixed", "b0und4ry_x", [_engine.build_text(_text()), parsed_child]
    )

    raw = _engine.to_bytes(multipart)
    assert multipart.get_boundary() == "b0und4ry_x"
    assert raw.count(b"--b0und4ry_x\r\n") == 2
    assert raw.endswith(b"--b0und4ry_x--\r\n")
    assert b"MIME-Version" not in raw


def test_add_header_appends_a_typed_header_to_a_part() -> None:
    part = _engine.build_text(_text())

    _engine.add_header(part, "X-Tag", "Héllo")

    assert list(part.keys())[-1] == "X-Tag"
    assert part["X-Tag"] == "Héllo"


def test_a_message_puts_its_own_headers_before_the_body_headers() -> None:
    body = _engine.build_text(_text())

    message = _engine.build_message(
        [("MIME-Version", "1.0"), ("Subject", "Héllo"), ("To", [Mailbox("", "b@example.com")])],
        body,
    )

    assert list(message.keys()) == [
        "MIME-Version",
        "Subject",
        "To",
        "Content-Type",
        "Content-Transfer-Encoding",
    ]
    assert message.get_content() == "Hello\n"


def _sample_message() -> _engine.EnginePart:
    alternative = _engine.build_multipart(
        "alternative",
        "alt_boundary",
        [
            _engine.build_text(_text("Héllo wörld")),
            _engine.build_text(_text("<p>Héllo</p>", subtype="html", transfer_encoding="base64")),
        ],
    )
    attachment = _engine.build_binary(
        BinaryLeaf(
            content=b"%PDF-1.4\x00\xff" * 40,
            maintype="application",
            subtype="pdf",
            transfer_encoding="base64",
            disposition=Parameterized("attachment", {"filename": "résumé.pdf"}),
        )
    )
    body = _engine.build_multipart("mixed", "mixed_boundary", [alternative, attachment])
    return _engine.build_message(
        [
            ("From", [Mailbox("Žluťoučký Kůň", "alice@dømi.fo")]),
            ("Subject", LONG_SUBJECT),
            ("Date", datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)),
            ("MIME-Version", "1.0"),
        ],
        body,
    )


def test_parsing_a_rendered_message_gives_back_its_structure_and_content() -> None:
    parsed = _engine.parse(_engine.to_bytes(_sample_message()))

    assert parsed.get_content_type() == "multipart/mixed"
    assert parsed["Subject"] == LONG_SUBJECT
    assert str(parsed["From"]) == "Žluťoučký Kůň <alice@xn--dmi-0na.fo>"
    alternative, attachment = parsed.iter_parts()
    text, html = alternative.iter_parts()
    assert alternative.get_boundary() == "alt_boundary"
    # Read back from the wire, a text body has the wire's CRLF line ends.
    assert text.get_content() == "Héllo wörld\r\n"
    assert html.get_content() == "<p>Héllo</p>\r\n"
    assert attachment.get_filename() == "résumé.pdf"
    assert attachment.get_content() == b"%PDF-1.4\x00\xff" * 40


def test_a_rendered_message_is_ascii_with_crlf_lines_of_at_most_76() -> None:
    raw = _engine.to_bytes(_sample_message())

    assert raw.isascii()
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert all(len(line) <= 76 for line in raw.split(b"\r\n"))


def test_a_body_line_starting_with_from_is_not_escaped() -> None:
    raw = _engine.to_bytes(_engine.build_text(_text("From here on", transfer_encoding="8bit")))

    assert raw.endswith(b"\r\n\r\nFrom here on\r\n")


def test_the_rendered_chunks_join_to_the_rendered_string() -> None:
    message = _sample_message()

    chunks = list(_engine.render(message))

    assert len(chunks) > 1
    assert all(type(chunk) is bytes for chunk in chunks)
    assert b"".join(chunks) == _engine.to_bytes(message)
    assert b"".join(chunks) == _engine.to_string(message).encode("utf-8", "surrogateescape")


def test_an_eight_bit_body_in_another_charset_survives_to_string() -> None:
    part = _engine.build_text(_text("Žluť", charset="iso-8859-2", transfer_encoding="8bit"))

    rendered = _engine.to_string(part)

    assert rendered.encode("utf-8", "surrogateescape") == _engine.to_bytes(part)
    assert _engine.to_bytes(part).endswith("Žluť\r\n".encode("iso-8859-2"))
