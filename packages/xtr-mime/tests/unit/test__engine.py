"""Characterisation of the stdlib ``email`` behaviours the rendering engine relies on.

xtr-mime hands all wire work to Python's ``email`` package. Every behaviour that choice depends
on is pinned here, so a change in a new Python release fails in this file first.
"""

from __future__ import annotations

import base64
import quopri
import random
import re
from datetime import UTC, datetime
from email import policy as stdlib_policy
from email.header import decode_header
from email.headerregistry import Address, AddressHeader, Group
from email.message import EmailMessage
from email.parser import BytesParser, HeaderParser
from typing import TYPE_CHECKING, cast

import pytest

from tests.support.wire import encoded_words
from xtr_mime import _engine
from xtr_mime._engine import (
    BinaryLeaf,
    Mailbox,
    MailboxGroup,
    MessageIds,
    Parameterized,
    Path,
    TextLeaf,
)
from xtr_mime._header_reader import read_unstructured
from xtr_mime.exception import (
    InvalidArgumentError,
    MimeError,
    MimeRuntimeError,
    RfcComplianceError,
)

if TYPE_CHECKING:
    from xtr_mime._engine import HeaderValue, TransferEncoding

LONG_SUBJECT = "Žluťoučký kůň úpěl ďábelské ódy, " * 5

# A display name that is itself an encoded word: a reader decoding it would see an address.
ENCODED_WORD_NAME = "=?utf-8?b?ZXZpbEBhdHRhY2tlci5jb20gPGV2aWxAYXR0YWNrZXIuY29tPg==?="

# Every C0 control but TAB, and DEL: none may reach a header, whatever the Python patch level.
CONTROL_CHARACTERS = ["\r", "\n", "\r\n", "\x00", "\x0b", "\x0c", "\x1b", "\x1f", "\x7f"]

# Line and paragraph separators, C1 controls (NEL among them) and a lone surrogate: some
# readers end a line at the first ones, and the last is a byte that was never text.
SEPARATORS = ["\u2028", "\u2029", "\x85", "\x80", "\x9f", "\ud800", "\udc80"]


def _decode(field: str) -> str:
    """Read one rendered header field back the way a mail client would."""
    name = field.split(":", 1)[0]
    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    return cast("str", parsed[name])


def _rfc2047(text: str) -> str:
    """Decode ``text`` as RFC 2047 says: whitespace between two encoded words is dropped."""
    parts: list[tuple[bytes | str, str | None]] = decode_header(text.replace("\r\n", ""))
    return "".join(
        part.decode(charset or "ascii") if isinstance(part, bytes) else part
        for part, charset in parts
    )


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


LONG_UNSUBSCRIBE = "<https://example.com/u/" + "a" * 120 + ">"
LONG_VARIABLES = '{"k":"' + "v" * 200 + '"}'


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("List-Unsubscribe", LONG_UNSUBSCRIBE),
        ("X-Mailgun-Variables", LONG_VARIABLES),
        ("Subject", "x" * 300),
    ],
)
def test_an_ascii_word_too_long_for_a_line_is_written_plain_on_a_line_of_its_own(
    name: str, value: str
) -> None:
    assert _engine.fold_header(name, value) == f"{name}:\r\n {value}"


def test_a_short_ascii_value_stays_on_the_name_line() -> None:
    field = _engine.fold_header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click")

    assert field == "List-Unsubscribe-Post: List-Unsubscribe=One-Click"


@pytest.mark.parametrize("line_length", [997, 998])
def test_a_plain_word_may_fill_its_line_up_to_998_octets(line_length: int) -> None:
    word = "x" * (line_length - 1)

    field = _engine.fold_header("X-A", word)

    assert _lines(field) == ["X-A:", f" {word}"]


def test_a_plain_word_that_would_make_a_line_of_999_octets_is_refused_without_quoting_it() -> None:
    word = "x" * 998

    with pytest.raises(RfcComplianceError, match="998") as raised:
        _ = _engine.fold_header("X-A", word)

    assert "xxxx" not in str(raised.value)


def test_only_the_non_ascii_words_of_a_text_with_a_long_token_are_encoded() -> None:
    token = "t" * 100
    value = f"hello there {token} and wörld after"

    field = _engine.fold_header("Subject", value)

    assert f"\r\n {token}\r\n" in field
    assert [_rfc2047(word) for word in encoded_words(field)] == ["wörld"]
    assert _decode(field) == value


def test_a_long_token_between_non_ascii_words_stays_plain() -> None:
    token = "t" * 100
    value = f"Žluťoučký kůň {token} úpěl"

    field = _engine.fold_header("Subject", value)

    assert f"\r\n {token}\r\n" in field
    assert _rfc2047(field.split(":", 1)[1]).strip() == value


@pytest.mark.parametrize(
    "value",
    [
        "Žluťoučký kůň " + "t" * 100 + " úpěl",
        "a  Ž\tŽ  b =?x?= " + "t" * 80 + "\tc",
        LONG_SUBJECT,
    ],
)
def test_the_engine_written_text_decodes_back_with_its_ascii_words_plain(value: str) -> None:
    """What the engine writes when the package's folding would not read back, tried directly."""
    folded = _engine._write_text("Subject", value)

    _engine._check_folded(folded)
    field = folded.removesuffix("\r\n")
    # Whitespace around the value is dropped, as the package drops it.
    assert _rfc2047(field.split(":", 1)[1]).strip() == value.strip()
    assert all(len(line) <= 76 for line in _lines(field) if "t" * 80 not in line)
    plain = re.sub(r"=\?.+?\?=", "", field)
    assert all(word in plain for word in value.split() if word.isascii() and "=?" not in word)
    # Text a reader takes for an encoded word is encoded, so it reads back as written.
    assert "=?x?=" not in field


def test_a_line_break_in_a_value_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("Subject", "Hi\r\nBcc: victim@example.com")


@pytest.mark.parametrize("control", CONTROL_CHARACTERS)
def test_a_control_character_in_unstructured_text_is_refused(control: str) -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("Subject", f"Hi{control}there")


def test_a_tab_in_unstructured_text_is_kept() -> None:
    assert _decode(_engine.fold_header("Subject", "a\tb")) == "a\tb"


def test_an_encoded_word_that_decodes_to_a_line_break_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("Subject", "=?utf-8?q?Hi=0D=0ABcc:_x@example.com?=")


def test_an_encoded_word_in_unstructured_text_is_written_as_the_text_it_is() -> None:
    """The engine alone would decode ``=?...?=`` in a value; a reader must see the value."""
    field = _engine.fold_header("Subject", "=?utf-8?q?h=C3=A9llo?=")

    assert _rfc2047(field.split(":", 1)[1]).strip() == "=?utf-8?q?h=C3=A9llo?="
    assert _decode(field) == "=?utf-8?q?h=C3=A9llo?="


@pytest.mark.parametrize("name", ["", "Sub ject", "Sub\tject", "Sub\r\nject", "Šubject", "a\x7f"])
def test_a_header_name_that_is_not_printable_ascii_is_refused(name: str) -> None:
    with pytest.raises(RfcComplianceError, match="header name"):
        _ = _engine.fold_header(name, "value")


# A reader ends a name at its first colon: the last one would be read as a Bcc header.
COLON_NAMES = ["h:Sender", "o:tag", "v:version", "Bcc:victim@example.com,x"]


@pytest.mark.parametrize("name", COLON_NAMES)
def test_a_header_name_holding_a_colon_is_never_folded_for_the_wire(name: str) -> None:
    with pytest.raises(RfcComplianceError, match=re.escape(repr(name))):
        _ = _engine.fold_header(name, "value")


@pytest.mark.parametrize("name", COLON_NAMES)
def test_a_header_name_holding_a_colon_is_never_added_to_a_part(name: str) -> None:
    with pytest.raises(RfcComplianceError, match=re.escape(repr(name))):
        _ = _render_with(name, "value")


@pytest.mark.parametrize("name", COLON_NAMES)
def test_a_header_name_holding_a_colon_is_never_rendered(name: str) -> None:
    part = _engine.build_text(_text())
    part.set_raw(name, "value")

    with pytest.raises(RfcComplianceError, match=re.escape(repr(name))):
        _ = _engine.to_bytes(part)


@pytest.mark.parametrize("name", COLON_NAMES)
def test_the_body_of_a_header_named_with_a_colon_is_rendered_for_a_transport(name: str) -> None:
    assert _engine.header_body(name, '{"a":1}') == '{"a":1}'


def test_a_continuation_line_without_leading_space_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="continuation"):
        _engine._check_folded("Subject: a\r\nBcc: victim@example.com\r\n")


def test_a_folded_field_must_end_with_its_line_break() -> None:
    with pytest.raises(RfcComplianceError, match="continuation"):
        _engine._check_folded("Subject: a\nBcc: victim@example.com")


@pytest.mark.parametrize("character", ["\x00", "\x0b", "\x0c", "\x1c", "\x7f", *SEPARATORS])
def test_a_folded_field_holding_a_control_character_is_refused(character: str) -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _engine._check_folded(f"Subject: a{character}Bcc: victim@example.com\r\n")


def test_a_folded_field_keeps_its_tabs() -> None:
    _engine._check_folded("Subject: a\tb\r\n\tc\r\n")


def test_a_folded_line_longer_than_998_octets_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="998"):
        _engine._check_folded("Subject: " + "ø" * 500 + "\r\n")


@pytest.mark.parametrize(
    "value",
    [
        [Mailbox("a" * 5000, "a@example.com")],
        [MailboxGroup("g, " * 2000, ())],
        [Mailbox("", "a" * 1000 + "@example.com")],
    ],
)
def test_an_address_header_with_a_line_longer_than_998_is_refused(value: HeaderValue) -> None:
    with pytest.raises(RfcComplianceError, match="998"):
        _ = _engine.fold_header("To", value)


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


INJECTED_FILENAME = "a.txt\r\nBcc: x@y.z"


def test_a_line_break_in_a_disposition_filename_is_refused_on_the_wire() -> None:
    leaf = BinaryLeaf(
        content=b"x",
        maintype="application",
        subtype="octet-stream",
        transfer_encoding="base64",
        disposition=Parameterized("attachment", {"filename": INJECTED_FILENAME}),
    )

    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.to_bytes(_engine.build_binary(leaf))


@pytest.mark.parametrize("control", CONTROL_CHARACTERS)
def test_a_control_character_in_a_content_type_parameter_is_refused(control: str) -> None:
    leaf = BinaryLeaf(
        content=b"x",
        maintype="application",
        subtype="octet-stream",
        transfer_encoding="base64",
        parameters={"name": f"a{control}b"},
    )

    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.to_bytes(_engine.build_binary(leaf))


def test_a_control_character_in_a_text_leaf_parameter_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.build_text(_text(parameters={"name": INJECTED_FILENAME}))


@pytest.mark.parametrize(
    "name", ["", "file name", "a\r\nb", "x*", "x'", "x%", "a=b", 'a"b', "a;b", "nàme", "a\x00"]
)
def test_a_parameter_name_that_is_not_an_rfc_2231_token_is_refused(name: str) -> None:
    with pytest.raises(RfcComplianceError, match="parameter name"):
        _ = _engine.fold_header("Content-Disposition", Parameterized("attachment", {name: "x"}))


@pytest.mark.parametrize("value", ["", "attach ment", "a\r\nb", "a;b", "inlïne"])
def test_a_disposition_that_is_not_a_token_is_refused(value: str) -> None:
    with pytest.raises(RfcComplianceError, match="token"):
        _ = _engine.fold_header("Content-Disposition", Parameterized(value))


@pytest.mark.parametrize("value", ["text", "text/", "/plain", "text/pl ain", "a/b/c", "té/x"])
def test_a_content_type_that_is_not_type_slash_subtype_is_refused(value: str) -> None:
    with pytest.raises(RfcComplianceError, match="media type"):
        _ = _engine.fold_header("Content-Type", Parameterized(value))


def test_a_long_identifier_is_written_whole_never_as_an_encoded_word() -> None:
    identifier = "c" * 90 + "@example.com"

    assert _engine.fold_header("Content-ID", MessageIds((identifier,))) == (
        f"Content-ID: <{identifier}>"
    )


def test_identifiers_fold_only_between_ids() -> None:
    ids = tuple(f"{index:02d}{'x' * 25}@example.com" for index in range(6))

    field = _engine.fold_header("References", MessageIds(ids))

    lines = _lines(field)
    assert len(lines) > 1
    assert all(len(line) <= 76 for line in lines)
    assert all(line.startswith(" <") and line.endswith(">") for line in lines[1:])
    assert field.replace("\r\n", "") == "References: " + " ".join(f"<{i}>" for i in ids)


def test_the_identifier_body_has_no_name_and_no_leading_space() -> None:
    assert _engine.header_body("Message-ID", MessageIds(("a@b",))) == "<a@b>"


def test_short_identifiers_share_a_line() -> None:
    field = _engine.fold_header("In-Reply-To", MessageIds(("a@b", "c@d")))

    assert field == "In-Reply-To: <a@b> <c@d>"


@pytest.mark.parametrize(
    "identifier", ["", "a b@x", "a<b@x", "a>b@x", "a\r\nb@x", "a\tb@x", "é@x", "a\x7f@x"]
)
def test_an_identifier_with_a_space_bracket_or_control_is_refused(identifier: str) -> None:
    with pytest.raises(RfcComplianceError, match="identifier"):
        _ = _engine.fold_header("Message-ID", MessageIds((identifier,)))


@pytest.mark.parametrize(
    "identifier",
    ["a@b", "a.b+&%$.c@d", "a@b.c+&%$.d", '"ab"@c', '"a@b"@c', "a@[1.2.3.4]", "a@[x:y]"],
)
def test_an_identifier_of_the_msg_id_grammar_is_accepted(identifier: str) -> None:
    _engine.check_message_id(identifier)

    assert _engine.header_body("Message-ID", MessageIds((identifier,))) == f"<{identifier}>"


@pytest.mark.parametrize(
    "identifier",
    [
        "abc",
        "a@b@c",
        "a..b@c",
        ".a@c",
        "a@b.",
        '"a\\<\\>b"@c',
        '"a<b"@c',
        '"a b"@c',
        '""@c',
        "a@[x<y]",
        "a@[x\\y]",
        "a@b c",
        "a@é",
    ],
)
def test_an_identifier_outside_the_msg_id_grammar_is_refused(identifier: str) -> None:
    with pytest.raises(RfcComplianceError, match="identifier"):
        _engine.check_message_id(identifier)


def test_an_identifier_holding_a_quoted_pair_never_reaches_the_wire() -> None:
    """Why an id holds no quoted pair: it reads back without its backslash, as another id."""
    with pytest.raises(RfcComplianceError, match="identifier"):
        _ = _render_with("Message-ID", MessageIds(('"a\\<\\>b"@c',)))


def test_an_identifier_header_needs_at_least_one_identifier() -> None:
    with pytest.raises(RfcComplianceError, match="identifier"):
        _ = _engine.fold_header("References", MessageIds(()))


def test_an_identifier_longer_than_a_line_may_be_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="998"):
        _ = _engine.fold_header("Message-ID", MessageIds(("x" * 990 + "@example.com",)))


def test_an_identifier_header_reads_back_through_the_engine() -> None:
    message = _engine.build_message(
        [("Message-ID", MessageIds(("a" * 80 + "@example.com",)))], _engine.build_text(_text())
    )

    raw = _engine.to_bytes(message)

    assert raw.startswith(b"Message-ID: <" + b"a" * 80 + b"@example.com>\r\n")
    assert _engine.parse(raw)["Message-ID"] == "<" + "a" * 80 + "@example.com>"


def test_a_path_is_an_angle_bracketed_address_with_its_domain_in_punycode() -> None:
    assert _engine.fold_header("Return-Path", Path("chris@swïftmailer.org")) == (
        "Return-Path: <chris@xn--swftmailer-78a.org>"
    )


def test_a_path_with_a_non_ascii_local_part_is_written_as_raw_utf8() -> None:
    raw = _render_with("Return-Path", Path("chrïs@swïftmailer.org"))

    assert raw.startswith("Return-Path: <chrïs@xn--swftmailer-78a.org>\r\n".encode())


@pytest.mark.parametrize(
    "address", ["chr is@example.com", "no-domain", "a@b@c", "a@=?utf-8?q?x?=", "a\r\nb@example.com"]
)
def test_a_path_that_is_not_an_address_is_refused(address: str) -> None:
    with pytest.raises(RfcComplianceError):
        _ = _engine.fold_header("Return-Path", Path(address))


@pytest.mark.parametrize(
    ("value", "written"),
    [
        ([Mailbox("Alice", "alice@dømi.fo")], "To: Alice <alice@xn--dmi-0na.fo>"),
        (
            [MailboxGroup("Team", (Mailbox("Alice", "alice@dømi.fo"),))],
            "To: Team: Alice <alice@xn--dmi-0na.fo>;",
        ),
    ],
)
def test_a_unicode_domain_never_reaches_the_wire_as_an_encoded_word(
    value: HeaderValue, written: str
) -> None:
    """CPython gh-83938: the package writes a raw Unicode domain as an encoded word.

    No server accepts that address. Whether or not the release still does it, the engine
    punycodes every domain before the package sees it, a group member's included.
    """
    assert _render_with("To", value).startswith(f"{written}\r\n".encode())


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


@pytest.mark.parametrize("control", CONTROL_CHARACTERS)
def test_a_control_character_in_a_display_name_is_refused(control: str) -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("To", [Mailbox(f"a{control}b", "bob@example.com")])


@pytest.mark.parametrize("control", CONTROL_CHARACTERS)
def test_a_control_character_in_a_group_name_is_refused(control: str) -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("To", [MailboxGroup(f"a{control}b", ())])


@pytest.mark.parametrize("control", CONTROL_CHARACTERS)
def test_a_control_character_in_an_address_is_refused(control: str) -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("To", [Mailbox("", f"bob{control}@example.com")])


def test_a_display_name_that_decodes_to_another_address_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="literal"):
        _ = _engine.fold_header("Reply-To", [Mailbox(ENCODED_WORD_NAME, "real@example.com")])


def test_a_group_name_that_decodes_to_another_address_is_refused() -> None:
    # Decodes to "x: evil@attacker.com;": a group of its own, holding another address.
    name = "=?utf-8?q?x=3A_evil=40attacker=2Ecom=3B?="

    with pytest.raises(RfcComplianceError, match="literal"):
        _ = _engine.fold_header("To", [MailboxGroup(name, (Mailbox("", "real@example.com"),))])


@pytest.mark.parametrize("address", ["real@=?utf-8?q?attacker.com?=", "=?utf-8?q?x?=@example.com"])
def test_an_address_holding_an_encoded_word_is_refused(address: str) -> None:
    """The engine would decode it: ``real@=?utf-8?q?attacker.com?=`` reads ``real@attacker.com``."""
    with pytest.raises(RfcComplianceError, match="encoded word"):
        _ = _engine.fold_header("To", [Mailbox("", address)])


@pytest.mark.parametrize("separator", SEPARATORS)
def test_a_line_separator_in_a_display_name_is_refused(separator: str) -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("To", [Mailbox(f"Dømi{separator}Bcc: x", "dømi@dømi.fo")])
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("To", [Mailbox(f"Dømi{separator}Bcc: x", "a@example.com")])
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("To", [MailboxGroup(f"g{separator}x", ())])


@pytest.mark.parametrize("separator", SEPARATORS)
def test_a_line_separator_in_any_other_header_value_is_refused(separator: str) -> None:
    values: list[tuple[str, HeaderValue]] = [
        ("Subject", f"a{separator}b"),
        ("To", [Mailbox("", f"a{separator}b@example.com")]),
        ("Content-Disposition", Parameterized("attachment", {"filename": f"a{separator}b"})),
        ("Message-ID", MessageIds((f"a{separator}b@example.com",))),
        ("Return-Path", Path(f"a{separator}b@example.com")),
    ]
    for name, value in values:
        with pytest.raises(RfcComplianceError):
            _ = _engine.fold_header(name, value)


def test_a_group_named_like_the_two_halves_of_an_encoded_word_is_refused() -> None:
    value = [MailboxGroup("=?utf-8?b?", ()), MailboxGroup("?=", ())]

    with pytest.raises(RfcComplianceError):
        _ = _engine.fold_header("To", value)


@pytest.mark.parametrize(
    "value",
    [
        [MailboxGroup("Žluťoučký <evil@attacker.com>", ()), Mailbox("", "a@b.cz")],
        [MailboxGroup('"x.' * 2000, ()), Mailbox("", "a@b.cz")],
        [MailboxGroup('"x.' * 20, (Mailbox("", "a@b.cz"),))],
        [Mailbox("a\udc80b", "a@b.cz")],
    ],
)
def test_a_name_the_engine_cannot_fold_is_written_faithfully_or_refused(value: HeaderValue) -> None:
    """Some patch releases crash or mis-fold on these; the engine's own error comes out instead."""
    try:
        field = _engine.fold_header("To", value)
    except RfcComplianceError:
        return

    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    header = cast("AddressHeader", parsed["To"])
    assert [a.addr_spec for a in header.addresses] == ["a@b.cz"]


LONG_NAME = ("Žluťoučký kůň úpěl ďábelské ódy " * 4).strip()


@pytest.mark.parametrize(
    "name",
    [
        LONG_NAME,
        "Hi Žluť",
        "Žluť Hi",
        "Žluťoučký <evil@attacker.com>",
        "Jean\tDupont Ž",
        "a  Ž  b",
        'Ž "quoted" \\ Ž',
        "ŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽ ŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽŽ",
    ],
)
def test_a_display_name_decodes_back_exactly_as_rfc_2047_reads_it(name: str) -> None:
    """Python 3.11 and 3.12.0 fold a long name so a reader joins two of its words.

    They write the space between two words as the fold between two encoded words, which an
    RFC 2047 reader drops; the engine writes such a name itself.
    """
    field = _engine.fold_header("To", [Mailbox(name, "a@example.com"), Mailbox(name, "b@c.cz")])

    # RFC 5322's recommended limit: the engine may run a line a little past its 76 columns.
    assert all(len(line) <= 78 for line in _lines(field))
    # The whitespace after a comma is the list's, not a name's: its width does not matter.
    decoded = re.sub(r", +", ", ", _rfc2047(field.split(":", 1)[1]).strip())
    assert decoded == f"{name} <a@example.com>, {name} <b@c.cz>"


@pytest.mark.parametrize("name", [LONG_NAME, "Hi Žluť", "Žluťoučký <evil@attacker.com>"])
def test_a_group_name_decodes_back_exactly_as_rfc_2047_reads_it(name: str) -> None:
    field = _engine.fold_header("To", [MailboxGroup(name, (Mailbox("", "a@example.com"),))])

    assert all(len(line) <= 78 for line in _lines(field))
    assert _rfc2047(field.split(":", 1)[1]).strip() == f"{name}: a@example.com;"


@pytest.mark.parametrize("subject", [LONG_NAME, "a  Ž  b", "Ž\tŽ", "Ž lead", "x" * 200 + " Ž"])
def test_an_unstructured_value_decodes_back_exactly_as_rfc_2047_reads_it(subject: str) -> None:
    field = _engine.fold_header("Subject", subject)

    assert _rfc2047(field.split(":", 1)[1]).strip() == subject


def test_the_engine_written_address_list_decodes_back_on_every_version() -> None:
    """What the engine writes when the package's folding would not read back, tried directly."""
    value: list[Mailbox | MailboxGroup] = [
        Mailbox(LONG_NAME, "a@example.com"),
        MailboxGroup("Tým, x", (Mailbox("Jean\tDupont", "b@example.com"), Mailbox("", "c@b.cz"))),
        MailboxGroup("nobody", ()),
        Mailbox("Bob", "d@example.com"),
    ]
    items = [_engine._to_engine_address(item) for item in value]

    folded = _engine._write_address_list("To", items, utf8=False)

    _engine._check_folded(folded)
    assert all(len(line) <= 76 for line in _lines(folded.removesuffix("\r\n")))
    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(folded + "\r\n")
    groups = cast("AddressHeader", parsed["To"]).groups
    read = [
        (g.display_name and g.display_name.strip(), [a.addr_spec for a in g.addresses])
        for g in groups
    ]
    assert read == [
        (None, ["a@example.com"]),
        ("Tým, x", ["b@example.com", "c@b.cz"]),
        ("nobody", []),
        (None, ["d@example.com"]),
    ]
    assert _rfc2047(folded.split(":", 1)[1]).startswith(f"{LONG_NAME} <a@example.com>,")


def test_the_engine_written_address_list_keeps_a_raw_utf8_name_raw() -> None:
    value: list[Mailbox | MailboxGroup] = [Mailbox("Dømi Ž", "dømi@dømi.fo")]
    items = [_engine._to_engine_address(item) for item in value]

    assert _engine._write_address_list("To", items, utf8=True) == (
        "To: Dømi Ž <dømi@xn--dmi-0na.fo>\r\n"
    )


def test_the_header_some_releases_write_for_an_encoded_word_name_is_refused() -> None:
    """Why names are kept literal: some releases write this one decoded and unquoted.

    3.11.5 and 3.12.0 among them write the header below, which reads as another recipient.
    Whatever the release, the engine refuses the name before the package sees it, and would
    refuse that header too.
    """
    given = [Address(ENCODED_WORD_NAME, addr_spec="real@example.com")]
    written = "Reply-To: evil@attacker.com <evil@attacker.com> <real@example.com>\r\n"

    with pytest.raises(RfcComplianceError, match="read back"):
        _engine._check_reads_back("Reply-To", given, written)


def test_a_folded_address_header_reading_back_to_other_addresses_is_refused() -> None:
    given = [Address("", addr_spec="real@example.com")]

    with pytest.raises(RfcComplianceError, match="read back"):
        _engine._check_reads_back("To", given, "To: evil@attacker.com <evil@attacker.com>\r\n")


def test_a_folded_address_header_reading_back_ungrouped_is_refused() -> None:
    given = [Group("g", [Address("", addr_spec="real@example.com")])]

    with pytest.raises(RfcComplianceError, match="read back"):
        _engine._check_reads_back("To", given, "To: real@example.com\r\n")


@pytest.mark.parametrize("name", ["=?utf-8?q?hello?=", "Hi =?utf-8?b?aGk=?= there"])
def test_a_display_name_holding_an_encoded_word_is_refused(name: str) -> None:
    with pytest.raises(RfcComplianceError, match="literal"):
        _ = _engine.fold_header("To", [Mailbox(name, "real@example.com")])


def test_a_group_name_holding_an_encoded_word_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="literal"):
        _ = _engine.fold_header("To", [MailboxGroup("=?utf-8?q?hello?=", ())])


@pytest.mark.parametrize(
    "name",
    [
        "evil@attacker.com <evil@attacker.com>",
        "a, b <c@example.com>",
        "x: evil@attacker.com;",
        '"quoted" =? not an encoded word',
    ],
)
def test_an_address_list_reads_back_to_the_addresses_given_in_order(name: str) -> None:
    value: list[Mailbox | MailboxGroup] = [
        Mailbox(name, "first@example.com"),
        MailboxGroup(name, (Mailbox(name, "second@example.com"),)),
        Mailbox("", "third@example.com"),
    ]

    field = _engine.fold_header("To", value)

    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    header = cast("AddressHeader", parsed["To"])
    assert [a.addr_spec for a in header.addresses] == [
        "first@example.com",
        "second@example.com",
        "third@example.com",
    ]
    # The header parser keeps a space before a group name it decodes; a reader drops it.
    assert [g.display_name and g.display_name.strip() for g in header.groups] == [None, name, None]


def test_a_non_ascii_local_part_is_written_as_raw_utf8() -> None:
    field = _engine.fold_header("To", [Mailbox("Dømi", "dømi@dømi.fo")])

    assert field == "To: Dømi <dømi@xn--dmi-0na.fo>"


NON_ASCII_NAME_WITH_AN_ADDRESS = "Žluťoučký <evil@attacker.com>"


def test_a_non_ascii_name_holding_an_address_reads_back() -> None:
    """Older patch releases (3.11.5 and 3.12.0 among them) mis-fold such a name.

    Their encoded words read as other addresses; the engine writes the field itself then.
    """
    value = [
        Mailbox(NON_ASCII_NAME_WITH_AN_ADDRESS, "a@example.com"),
        Mailbox(NON_ASCII_NAME_WITH_AN_ADDRESS, "b@example.com"),
    ]

    field = _engine.fold_header("To", value)

    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    header = cast("AddressHeader", parsed["To"])
    assert [a.addr_spec for a in header.addresses] == ["a@example.com", "b@example.com"]
    assert [a.display_name for a in header.addresses] == [NON_ASCII_NAME_WITH_AN_ADDRESS] * 2


def test_a_non_ascii_local_part_in_a_list_is_written_as_raw_utf8() -> None:
    field = _engine.fold_header("To", [Mailbox("", "a@b.cz"), Mailbox("", "dømi@dømi.fo")])

    assert field == "To: a@b.cz, dømi@xn--dmi-0na.fo"


def test_a_group_holding_a_non_ascii_local_part_is_written_as_raw_utf8() -> None:
    value = [MailboxGroup("Tým", (Mailbox("", "dømi@example.com"),)), Mailbox("", "a@b.cz")]

    assert _engine.header_body("To", value) == "Tým: dømi@example.com;, a@b.cz"


def test_a_message_with_a_non_ascii_local_part_renders_its_headers_in_utf8() -> None:
    message = _engine.build_message(
        [("To", [Mailbox("Dømi", "dømi@dømi.fo")]), ("Subject", "Héllo")],
        _engine.build_text(_text()),
    )

    raw = _engine.to_bytes(message)

    head = raw.split(b"\r\n\r\n", 1)[0].split(b"\r\n")
    assert head[0] == "To: Dømi <dømi@xn--dmi-0na.fo>".encode()
    # Only the header that needs it is raw UTF-8: the Subject stays an encoded word.
    assert head[1].isascii()
    parsed = BytesParser(policy=stdlib_policy.default).parsebytes(raw)
    assert parsed["Subject"] == "Héllo"


@pytest.mark.parametrize("address", ["dø mi@example.com", "dø@mi@example.com", "dø."])
def test_a_non_ascii_local_part_the_engine_cannot_parse_is_refused(address: str) -> None:
    with pytest.raises(RfcComplianceError, match="email address"):
        _ = _engine.fold_header("To", [Mailbox("", address)])


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


@pytest.mark.parametrize(
    "charset",
    ["utf-8\n", "utf-8\r\n", "utf-8\x0b", "utf-8\x0c", "utf-8\x1c", "utf-8\x00", "utf 8", ""],
)
def test_a_charset_that_is_not_a_token_is_refused(charset: str) -> None:
    with pytest.raises(RfcComplianceError, match="charset"):
        _ = _engine.build_text(_text(charset=charset))


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
            content_id="logo@xtr",
        )
    )

    assert part.get_content_type() == "image/png"
    assert part.get_content_disposition() == "inline"
    assert part.get_filename() == "logo.png"
    assert part["Content-ID"] == "<logo@xtr>"
    assert part.get_content() == b"\x89PNG\x00\xff"


def test_a_long_content_id_is_written_whole_on_the_wire() -> None:
    identifier = "c" * 90 + "@example.com"
    leaf = BinaryLeaf(
        content=b"x",
        maintype="image",
        subtype="png",
        transfer_encoding="base64",
        content_id=identifier,
    )

    raw = _engine.to_bytes(_engine.build_binary(leaf))

    assert f"\r\nContent-ID: <{identifier}>\r\n".encode() in raw


@pytest.mark.parametrize("token", ["", "pl ain", "pl\r\nain", "a/b", "é", "x;y"])
def test_a_media_type_part_that_is_not_a_token_is_refused(token: str) -> None:
    with pytest.raises(RfcComplianceError, match="token"):
        _ = _engine.build_binary(
            BinaryLeaf(content=b"x", maintype=token, subtype="x", transfer_encoding="base64")
        )
    with pytest.raises(RfcComplianceError, match="token"):
        _ = _engine.build_binary(
            BinaryLeaf(content=b"x", maintype="x", subtype=token, transfer_encoding="base64")
        )
    with pytest.raises(RfcComplianceError, match="token"):
        _ = _engine.build_text(_text(subtype=token))
    with pytest.raises(RfcComplianceError, match="token"):
        _ = _engine.build_multipart(token, "boundary", [])


def test_a_binary_quoted_printable_line_may_run_to_77_characters() -> None:
    """The engine's binary quoted-printable writer (``binascii.b2a_qp``) may break the 76 limit.

    A line feed right after 76 bytes gets a soft break after the 76th character, so that line
    is 77 long. Readers accept it; whether or not the release still does it, no line runs
    longer and the body decodes back.
    """
    content = b"a" * 76 + b"\n"
    leaf = BinaryLeaf(
        content=content, maintype="application", subtype="x", transfer_encoding="quoted-printable"
    )

    raw = _engine.to_bytes(_engine.build_binary(leaf))

    body = raw.split(b"\r\n\r\n", 1)[1]
    assert max(len(line) for line in body.split(b"\r\n")) <= 77
    assert quopri.decodestring(body) == content


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


@pytest.mark.parametrize(
    "boundary",
    ["", "a" * 71, "trailing ", 'a"b', "a\r\nb", "é", "a;b", "a\tb", "a@b", "=?x?=", "a=?b"],
)
def test_a_boundary_outside_rfc_2046_is_refused(boundary: str) -> None:
    with pytest.raises(RfcComplianceError, match="boundary"):
        _ = _engine.build_multipart("mixed", boundary, [])


@pytest.mark.parametrize("boundary", ["a" * 70, "with inner space", "'()+_,-./:?=09AZaz"])
def test_a_boundary_inside_rfc_2046_is_kept(boundary: str) -> None:
    assert _engine.build_multipart("mixed", boundary, []).get_boundary() == boundary


def test_add_header_appends_a_typed_header_to_a_part() -> None:
    part = _engine.build_text(_text())

    _engine.add_header(part, "X-Tag", "Héllo")

    assert list(part.keys())[-1] == "X-Tag"
    assert part["X-Tag"] == "Héllo"


def test_set_fields_carries_each_field_as_written_in_place_of_the_part_headers() -> None:
    part = _engine.build_text(_text())

    _engine.set_fields(part, ["X-Written: as\r\n given", "Content-Type: text/plain"])

    rendered = _engine.to_bytes(part)
    assert rendered.startswith(b"X-Written: as\r\n given\r\nContent-Type: text/plain\r\n\r\n")


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("X-Written", id="no colon"),
        pytest.param("X Written: value", id="not a name"),
        pytest.param("X-Written: a\r\nInjected: 1", id="a line of its own"),
        pytest.param("X-Written: a\x00b", id="a control character"),
    ],
)
def test_set_fields_refuses_a_field_that_is_not_one(field: str) -> None:
    part = _engine.build_text(_text())

    with pytest.raises(RfcComplianceError):
        _engine.set_fields(part, [field])


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


def test_a_message_around_a_parsed_body_carries_one_mime_version() -> None:
    body = _engine.parse(b"MIME-Version: 1.0\r\nContent-Type: text/plain\r\n\r\nhi\r\n")

    message = _engine.build_message([("MIME-Version", "1.0"), ("Subject", "x")], body)

    assert list(message.keys()) == ["MIME-Version", "Subject", "Content-Type"]
    assert _engine.to_bytes(message).count(b"MIME-Version") == 1


def test_a_message_keeps_the_body_mime_version_when_it_sets_none() -> None:
    body = _engine.parse(b"MIME-Version: 1.0\r\nContent-Type: text/plain\r\n\r\nhi\r\n")

    message = _engine.build_message([("Subject", "x")], body)

    assert list(message.keys()) == ["Subject", "MIME-Version", "Content-Type"]


def test_a_message_does_not_share_the_body_part_list() -> None:
    body = _engine.build_multipart("mixed", "b", [_engine.build_text(_text())])

    message = _engine.build_message([], body)
    message.attach(_engine.build_text(_text()))

    assert len(list(body.iter_parts())) == 1
    assert len(list(message.iter_parts())) == 2


def _render_with(name: str, value: HeaderValue) -> bytes:
    return _engine.to_bytes(_engine.build_message([(name, value)], _engine.build_text(_text())))


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("Subject", "Hi\r\nBcc: x@y.z"),
        ("Subject", "Hi\nBcc: x@y.z"),
        ("Subject", "Hi\x00there"),
        ("Subject", "=?utf-8?q?Hi=0D=0ABcc:_x@y.z?="),
        ("To", [Mailbox("a\r\nBcc: x@y.z", "b@example.com")]),
        ("To", [Mailbox("", "b@example.com\r\nBcc: x@y.z")]),
        ("To", [MailboxGroup("g\r\nBcc: x@y.z", ())]),
        ("Reply-To", [Mailbox(ENCODED_WORD_NAME, "real@example.com")]),
        ("Content-Disposition", Parameterized("attachment", {"filename": INJECTED_FILENAME})),
        ("Content-Disposition", Parameterized("attachment", {"a\r\nb": "x"})),
        ("Content-Disposition", Parameterized("attachment\r\nBcc: x@y.z")),
        ("Message-ID", MessageIds(("a@b>\r\nBcc: x@y.z",))),
        ("Subject\r\nBcc", "x"),
    ],
)
def test_every_injection_probe_is_refused_before_it_reaches_the_wire(
    name: str, value: HeaderValue
) -> None:
    with pytest.raises(RfcComplianceError):
        _ = _render_with(name, value)


def test_parsing_pathologically_nested_input_is_a_mime_runtime_error() -> None:
    data = b"".join(
        b"Content-Type: multipart/mixed; boundary=b%d\r\n\r\n--b%d\r\n" % (level, level)
        for level in range(2000)
    )

    with pytest.raises(MimeRuntimeError, match="nested"):
        _ = _engine.parse(data + b"\r\nx\r\n")


@pytest.mark.parametrize(
    "character", [b"\x0b", b"\x0c", b"\x1c", b"\x00", b"\x85", "\u2028".encode()]
)
def test_a_parsed_header_holding_a_control_character_is_refused_when_rendered(
    character: bytes,
) -> None:
    """Before CVE-2024-6923 was fixed the engine wrote ``\\x0b`` here as a line break."""
    raw = (
        b"X-A: a" + character + b"Bcc: evil@attacker.com\r\nContent-Type: text/plain\r\n\r\nhi\r\n"
    )
    parsed = _engine.parse(raw)

    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.to_bytes(parsed)
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.to_bytes(_engine.build_message([("Subject", "x")], parsed))
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.to_bytes(_engine.build_multipart("mixed", "b", [parsed]))


def test_a_parsed_header_with_a_name_that_is_not_one_is_refused_when_rendered() -> None:
    parsed = _engine.parse(b"Content-Type: text/plain\r\n\r\nhi\r\n")
    parsed.set_raw("X A", "x")

    with pytest.raises(RfcComplianceError, match="header name"):
        _ = _engine.to_bytes(parsed)


def test_a_parsed_multipart_with_an_empty_boundary_is_refused_when_rendered() -> None:
    """The engine would make up a boundary and rewrite Content-Type from what it decoded."""
    parsed = _engine.parse(
        b'Content-Type: multipart/mixed; boundary=""; name="=?utf-8?q?a=00b?="\r\n\r\n'
        b"--\r\nContent-Type: text/plain\r\n\r\nhi\r\n----\r\n"
    )

    with pytest.raises(RfcComplianceError, match="boundary"):
        _ = _engine.to_bytes(parsed)


def test_a_multipart_whose_fields_drop_the_boundary_is_refused_when_rendered() -> None:
    multipart = _engine.build_multipart("mixed", "b", [_engine.build_text(_text())])
    _engine.set_fields(multipart, ["Content-Type: multipart/mixed"])

    with pytest.raises(RfcComplianceError, match="boundary"):
        _ = _engine.to_bytes(multipart)


def test_a_header_line_under_multipart_signed_is_kept_within_998_octets() -> None:
    """The engine writes a signed subtree unfolded, so the line is checked as written."""
    leaf = _engine.build_text(_text(parameters={"name": "a" * 2000}))

    with pytest.raises(RfcComplianceError, match="998"):
        _ = _engine.to_bytes(_engine.build_multipart("signed", "b", [leaf]))


def test_a_multipart_signed_renders_its_parts_as_built() -> None:
    leaf = _engine.build_text(_text(LONG_SUBJECT))

    rendered = _engine.to_bytes(_engine.build_multipart("signed", "b", [leaf]))

    assert _engine.to_bytes(leaf) in rendered


def test_a_parsed_address_header_is_written_as_read() -> None:
    """Some releases refold it by decoding the name: it then reads as another address."""
    field = f"Reply-To: {ENCODED_WORD_NAME} <real@example.com>".encode()
    parsed = _engine.parse(field + b"\r\nContent-Type: text/plain\r\n\r\nhi\r\n")

    rendered = _engine.to_bytes(parsed)

    assert rendered.startswith(field + b"\r\n")
    reply_to = _engine.parse(rendered)["Reply-To"]
    assert [a.addr_spec for a in cast("AddressHeader", reply_to).addresses] == ["real@example.com"]


def test_a_parsed_address_header_written_as_other_addresses_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="addresses"):
        _engine._check_addresses_kept(
            "Reply-To", "evil <real@example.com>", "Reply-To: evil@attacker.com\r\n"
        )


def test_a_parsed_address_header_written_as_the_same_addresses_is_kept() -> None:
    _engine._check_addresses_kept(
        "Reply-To", "Name <real@example.com>", "Reply-To:\r\n Name <real@example.com>\r\n"
    )


def test_an_encoded_word_naming_a_codec_that_is_not_text_is_written_as_the_text_it_is() -> None:
    value = "=?utf-8?q?=3D=3Fzlib=3Fq=3Fx=3F=3D?="

    field = _engine.fold_header("Subject", value)

    assert read_unstructured(field.removeprefix("Subject:")) == value


@pytest.mark.parametrize(
    "filename",
    [
        "=?utf-8?q?x=0BContent-Type:_text/html?=",
        "=?utf-8?q?x=0D=0ABcc:_evil@attacker.com?=",
        "=?utf-8?b?eAtCY2M6IGV2aWxAYXR0YWNrZXIuY29t?=",
        "=?utf-8?q?x=E2=80=A8y?=",
    ],
)
def test_an_encoded_word_in_a_parameter_decoding_to_a_control_character_is_refused(
    filename: str,
) -> None:
    disposition = Parameterized("attachment", {"filename": filename})
    leaf = BinaryLeaf(
        content=b"x",
        maintype="application",
        subtype="octet-stream",
        transfer_encoding="base64",
        disposition=disposition,
    )

    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("Content-Disposition", disposition)
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("Content-Type", Parameterized("text/plain", {"name": filename}))
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.to_bytes(_engine.build_binary(leaf))


_FUZZ_PIECES = (
    "a", "Ž", "ø", " ", "  ", "\t", '"', "\\", "<", ">", "@", ",", ";", ":", ".", "(", ")", "[",
    "]", "=?", "?=", "=?utf-8?b?", "=?utf-8?q?", "?q?", "?b?", "_", "=0A", "=0D", "=0B", "=C5",
    "\r\n", "\n", "\x0b", "\x00", "\x7f", "\x85", "\u2028", "\ud800", "x" * 80, "Bcc: ",
    "evil@attacker.com",
)  # fmt: skip

_FUZZ_ADDRESSES = ("a@example.com", "dømi@dømi.fo", '"q, r"@example.com', "u@[192.0.2.1]")


def _fuzz_text(rng: random.Random, longest: int = 12) -> str:
    return "".join(rng.choice(_FUZZ_PIECES) for _ in range(rng.randint(0, longest)))


def _fuzz_address(rng: random.Random) -> str:
    if rng.random() < 0.7:
        return rng.choice(_FUZZ_ADDRESSES)
    return _fuzz_text(rng, 4) + "@example.com"


def _fuzz_header(rng: random.Random) -> tuple[str, HeaderValue]:
    mailbox = Mailbox(_fuzz_text(rng), _fuzz_address(rng))
    choices: list[tuple[str, HeaderValue]] = [
        ("Subject", _fuzz_text(rng, 30)),
        ("To", [mailbox, Mailbox(_fuzz_text(rng), _fuzz_address(rng))]),
        ("To", [MailboxGroup(_fuzz_text(rng), (mailbox,)), MailboxGroup(_fuzz_text(rng), ())]),
        ("Content-Disposition", Parameterized("attachment", {"filename": _fuzz_text(rng)})),
        ("Content-Type", Parameterized("text/plain", {"name": _fuzz_text(rng)})),
        ("References", MessageIds((_fuzz_text(rng, 4) + "@example.com",))),
        ("Return-Path", Path(_fuzz_address(rng))),
        (_fuzz_text(rng, 2) or "X", "value"),
    ]
    return rng.choice(choices)


def test_only_the_engine_errors_ever_escape_writing_and_reading_headers() -> None:
    """A seeded fuzz: whatever a header holds, the engine writes it or raises its own error."""
    rng = random.Random(20261029)  # noqa: S311 -- a reproducible fuzz, not a secret
    body = _engine.build_text(_text())
    forbidden = set("\x00\x0b\x0c\x1c\x7f\x85\u2028\u2029")

    for _ in range(2000):
        name, value = _fuzz_header(rng)
        try:
            field = _engine.fold_header(name, value)
            raw = _engine.to_bytes(_engine.build_message([(name, value)], body))
            _ = _engine.to_bytes(_engine.parse(raw))
        except MimeError:
            continue
        assert not forbidden.intersection(field)


def test_only_the_engine_errors_ever_escape_parsing_and_rendering_bytes() -> None:
    rng = random.Random(29102026)  # noqa: S311 -- a reproducible fuzz, not a secret
    pieces = [piece.encode("utf-8", "surrogatepass") for piece in _FUZZ_PIECES]
    pieces += [b"\r\n", b"X-A: ", b"Content-Type: multipart/mixed; boundary=b\r\n", b"--b\r\n"]

    for _ in range(500):
        data = b"".join(rng.choice(pieces) for _ in range(rng.randint(0, 40)))
        try:
            _ = _engine.to_bytes(_engine.parse(data))
        except MimeError:
            continue


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
