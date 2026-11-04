"""Address headers: names and addresses that read back as given, on every Python release."""

from __future__ import annotations

import re
from email import policy as stdlib_policy
from email.headerregistry import Address, AddressHeader, Group
from email.parser import BytesParser, HeaderParser
from typing import TYPE_CHECKING, cast

import pytest

from tests.support.engine_cases import (
    ENCODED_WORD_NAME,
    LONG_NAME,
    lines_of,
    render_with,
    rfc2047,
    text_leaf,
)
from xtr_mime import _engine
from xtr_mime._engine import Mailbox, MailboxGroup
from xtr_mime._engine._address_list import check_reads_back, write_address_list
from xtr_mime._engine._addresses import to_engine_address
from xtr_mime._engine._grammar import check_folded
from xtr_mime.exception import RfcComplianceError

if TYPE_CHECKING:
    from xtr_mime._engine import HeaderValue


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
    assert render_with("To", value).startswith(f"{written}\r\n".encode())


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
    assert all(len(line) <= 78 for line in lines_of(field))
    # The whitespace after a comma is the list's, not a name's: its width does not matter.
    decoded = re.sub(r", +", ", ", rfc2047(field.split(":", 1)[1]).strip())
    assert decoded == f"{name} <a@example.com>, {name} <b@c.cz>"


@pytest.mark.parametrize("name", [LONG_NAME, "Hi Žluť", "Žluťoučký <evil@attacker.com>"])
def test_a_group_name_decodes_back_exactly_as_rfc_2047_reads_it(name: str) -> None:
    field = _engine.fold_header("To", [MailboxGroup(name, (Mailbox("", "a@example.com"),))])

    assert all(len(line) <= 78 for line in lines_of(field))
    assert rfc2047(field.split(":", 1)[1]).strip() == f"{name}: a@example.com;"


def test_the_engine_written_address_list_decodes_back_on_every_version() -> None:
    """What the engine writes when the package's folding would not read back, tried directly."""
    value: list[Mailbox | MailboxGroup] = [
        Mailbox(LONG_NAME, "a@example.com"),
        MailboxGroup("Tým, x", (Mailbox("Jean\tDupont", "b@example.com"), Mailbox("", "c@b.cz"))),
        MailboxGroup("nobody", ()),
        Mailbox("Bob", "d@example.com"),
    ]
    items = [to_engine_address(item) for item in value]

    folded = write_address_list("To", items, utf8=False)

    check_folded(folded)
    assert all(len(line) <= 76 for line in lines_of(folded.removesuffix("\r\n")))
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
    assert rfc2047(folded.split(":", 1)[1]).startswith(f"{LONG_NAME} <a@example.com>,")


def test_the_engine_written_address_list_keeps_a_raw_utf8_name_raw() -> None:
    value: list[Mailbox | MailboxGroup] = [Mailbox("Dømi Ž", "dømi@dømi.fo")]
    items = [to_engine_address(item) for item in value]

    assert write_address_list("To", items, utf8=True) == ("To: Dømi Ž <dømi@xn--dmi-0na.fo>\r\n")


def test_the_header_some_releases_write_for_an_encoded_word_name_is_refused() -> None:
    """Why names are kept literal: some releases write this one decoded and unquoted.

    3.11.5 and 3.12.0 among them write the header below, which reads as another recipient.
    Whatever the release, the engine refuses the name before the package sees it, and would
    refuse that header too.
    """
    given = [Address(ENCODED_WORD_NAME, addr_spec="real@example.com")]
    written = "Reply-To: evil@attacker.com <evil@attacker.com> <real@example.com>\r\n"

    with pytest.raises(RfcComplianceError, match="read back"):
        check_reads_back("Reply-To", given, written)


def test_a_folded_address_header_reading_back_to_other_addresses_is_refused() -> None:
    given = [Address("", addr_spec="real@example.com")]

    with pytest.raises(RfcComplianceError, match="read back"):
        check_reads_back("To", given, "To: evil@attacker.com <evil@attacker.com>\r\n")


def test_a_folded_address_header_reading_back_ungrouped_is_refused() -> None:
    given = [Group("g", [Address("", addr_spec="real@example.com")])]

    with pytest.raises(RfcComplianceError, match="read back"):
        check_reads_back("To", given, "To: real@example.com\r\n")


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
        _engine.build_text(text_leaf()),
    )

    raw = _engine.to_bytes(message)

    head = raw.split(b"\r\n\r\n", 1)[0].split(b"\r\n")
    assert head[0] == "To: Dømi <dømi@xn--dmi-0na.fo>".encode()
    # Only the header that needs it is raw UTF-8: the Subject stays an encoded word.
    assert head[1].isascii()
    parsed = BytesParser(policy=stdlib_policy.default).parsebytes(raw)
    assert parsed["Subject"] == "Héllo"
