"""Header fields: each kind of value folded, its body rendered, every probe refused."""

from __future__ import annotations

import random
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.support.engine_cases import (
    ENCODED_WORD_NAME,
    FUZZ_PIECES,
    INJECTED_FILENAME,
    LONG_SUBJECT,
    SEPARATORS,
    decode_field,
    lines_of,
    render_with,
    text_leaf,
)
from xtr_mime import _engine
from xtr_mime._engine import Mailbox, MailboxGroup, MessageIds, Parameterized, Path
from xtr_mime._engine._fold import add_header
from xtr_mime.exception import MimeError, RfcComplianceError

if TYPE_CHECKING:
    from xtr_mime._engine import HeaderValue

# A reader ends a name at its first colon: the last one would be read as a Bcc header.
COLON_NAMES = ["h:Sender", "o:tag", "v:version", "Bcc:victim@example.com,x"]


@pytest.mark.parametrize("name", COLON_NAMES)
def test_a_header_name_holding_a_colon_is_never_folded_for_the_wire(name: str) -> None:
    with pytest.raises(RfcComplianceError, match=re.escape(f'"{name}"')):
        _ = _engine.fold_header(name, "value")


@pytest.mark.parametrize("name", COLON_NAMES)
def test_a_header_name_holding_a_colon_is_never_added_to_a_part(name: str) -> None:
    with pytest.raises(RfcComplianceError, match=re.escape(f'"{name}"')):
        _ = render_with(name, "value")


@pytest.mark.parametrize("name", COLON_NAMES)
def test_a_header_name_holding_a_colon_is_never_rendered(name: str) -> None:
    part = _engine.build_text(text_leaf())
    part.set_raw(name, "value")

    with pytest.raises(RfcComplianceError, match=re.escape(f'"{name}"')):
        _ = _engine.to_bytes(part)


@pytest.mark.parametrize("name", COLON_NAMES)
def test_the_body_of_a_header_named_with_a_colon_is_rendered_for_a_transport(name: str) -> None:
    assert _engine.header_body(name, '{"a":1}') == '{"a":1}'


def test_the_header_body_is_the_folded_field_without_its_name() -> None:
    assert _engine.header_body("Subject", "plain value") == "plain value"
    assert _engine.header_body("X-Empty", "") == ""

    body = _engine.header_body("Subject", LONG_SUBJECT)
    assert "\r\n " in body
    assert decode_field("Subject: " + body) == LONG_SUBJECT


def test_a_body_folded_before_its_first_word_loses_the_leading_fold() -> None:
    body = _engine.header_body("From", [Mailbox("Žluťoučký Kůň " * 3, "alice@example.com")])

    assert not body.startswith(("\r\n", " "))


def test_a_date_header_is_written_in_rfc_5322_form() -> None:
    moment = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)

    assert _engine.header_body("Date", moment) == "Tue, 02 Jan 2024 03:04:05 +0000"


def test_a_long_identifier_is_written_whole_never_as_an_encoded_word() -> None:
    identifier = "c" * 90 + "@example.com"

    assert _engine.fold_header("Content-ID", MessageIds((identifier,))) == (
        f"Content-ID: <{identifier}>"
    )


def test_identifiers_fold_only_between_ids() -> None:
    ids = tuple(f"{index:02d}{'x' * 25}@example.com" for index in range(6))

    field = _engine.fold_header("References", MessageIds(ids))

    lines = lines_of(field)
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


def test_an_identifier_holding_a_quoted_pair_never_reaches_the_wire() -> None:
    """Why an id holds no quoted pair: it reads back without its backslash, as another id."""
    with pytest.raises(RfcComplianceError, match="identifier"):
        _ = render_with("Message-ID", MessageIds(('"a\\<\\>b"@c',)))


def test_an_identifier_header_needs_at_least_one_identifier() -> None:
    with pytest.raises(RfcComplianceError, match="identifier"):
        _ = _engine.fold_header("References", MessageIds(()))


def test_an_identifier_longer_than_a_line_may_be_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="998"):
        _ = _engine.fold_header("Message-ID", MessageIds(("x" * 990 + "@example.com",)))


def test_an_identifier_header_reads_back_through_the_engine() -> None:
    message = _engine.build_message(
        [("Message-ID", MessageIds(("a" * 80 + "@example.com",)))],
        _engine.build_text(text_leaf()),
    )

    raw = _engine.to_bytes(message)

    assert raw.startswith(b"Message-ID: <" + b"a" * 80 + b"@example.com>\r\n")
    assert _engine.parse(raw)["Message-ID"] == "<" + "a" * 80 + "@example.com>"


def test_a_path_is_an_angle_bracketed_address_with_its_domain_in_punycode() -> None:
    assert _engine.fold_header("Return-Path", Path("chris@swïftmailer.org")) == (
        "Return-Path: <chris@xn--swftmailer-78a.org>"
    )


def test_a_path_with_a_non_ascii_local_part_is_written_as_raw_utf8() -> None:
    raw = render_with("Return-Path", Path("chrïs@swïftmailer.org"))

    assert raw.startswith("Return-Path: <chrïs@xn--swftmailer-78a.org>\r\n".encode())


@pytest.mark.parametrize(
    "address", ["chr is@example.com", "no-domain", "a@b@c", "a@=?utf-8?q?x?=", "a\r\nb@example.com"]
)
def test_a_path_that_is_not_an_address_is_refused(address: str) -> None:
    with pytest.raises(RfcComplianceError):
        _ = _engine.fold_header("Return-Path", Path(address))


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


def test_add_header_appends_a_typed_header_to_a_part() -> None:
    part = _engine.build_text(text_leaf())

    add_header(part, "X-Tag", "Héllo")

    assert list(part.keys())[-1] == "X-Tag"
    assert part["X-Tag"] == "Héllo"


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
        _ = render_with(name, value)


_FUZZ_ADDRESSES = ("a@example.com", "dømi@dømi.fo", '"q, r"@example.com', "u@[192.0.2.1]")


def _fuzz_text(rng: random.Random, longest: int = 12) -> str:
    return "".join(rng.choice(FUZZ_PIECES) for _ in range(rng.randint(0, longest)))


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
    body = _engine.build_text(text_leaf())
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


def _has_blank_line(field: str) -> bool:
    return any(not line.strip(" \t") for line in field.split("\r\n")[1:])


@pytest.mark.parametrize(
    "value",
    [f"{'Invoice':<80}#123", [Mailbox(f"{'Invoice':<80}#123", "c@example.com")]],
    ids=["text", "address"],
)
def test_a_long_whitespace_run_is_never_folded_onto_a_line_of_its_own(value: HeaderValue) -> None:
    field = _engine.fold_header("To" if isinstance(value, list) else "Subject", value)

    assert not _has_blank_line(field)
    assert f"Invoice{' ' * 73}#123" in re.sub(r"\r\n(?=[ \t])", "", field)


def test_no_generated_subject_is_folded_onto_a_line_of_whitespace_alone() -> None:
    """A seeded sweep of subjects mixing words and whitespace runs of every length."""
    rng = random.Random(20261103)  # noqa: S311 -- a reproducible sweep, not a secret
    words = ["Invoice", "#123", "J\u00fcrgen", "x" * 70, "a"]
    body = _engine.build_text(text_leaf())

    for _ in range(2000):
        pieces = [rng.choice(words) + " " * rng.randint(1, 120) for _ in range(rng.randint(1, 4))]
        subject = "".join(pieces) + rng.choice(words)
        field = _engine.fold_header("Subject", subject)
        raw = _engine.to_bytes(_engine.build_message([("Subject", subject)], body))

        assert not _has_blank_line(field)
        assert not _has_blank_line(raw.partition(b"\r\n\r\n")[0].decode())
