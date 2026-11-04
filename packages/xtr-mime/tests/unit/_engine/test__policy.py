"""The engine's policy: CRLF, 76 columns, and every field checked as it is written."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from tests.support.engine_cases import ENCODED_WORD_NAME, LONG_SUBJECT, text_leaf
from xtr_mime import _engine
from xtr_mime._engine._policy import POLICY, check_addresses_kept
from xtr_mime.exception import RfcComplianceError

if TYPE_CHECKING:
    from email.headerregistry import AddressHeader


def test_the_policy_writes_crlf_and_folds_at_76_columns() -> None:
    assert POLICY.linesep == "\r\n"
    assert POLICY.max_line_length == 76
    assert POLICY.mangle_from_ is False


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


def test_a_header_line_under_multipart_signed_is_kept_within_998_octets() -> None:
    """The engine writes a signed subtree unfolded, so the line is checked as written."""
    leaf = _engine.build_text(text_leaf(parameters={"name": "a" * 2000}))

    with pytest.raises(RfcComplianceError, match="998"):
        _ = _engine.to_bytes(_engine.build_multipart("signed", "b", [leaf]))


def test_a_multipart_signed_renders_its_parts_as_built() -> None:
    leaf = _engine.build_text(text_leaf(LONG_SUBJECT))

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
        check_addresses_kept(
            "Reply-To", "evil <real@example.com>", "Reply-To: evil@attacker.com\r\n"
        )


def test_a_parsed_address_header_written_as_the_same_addresses_is_kept() -> None:
    check_addresses_kept(
        "Reply-To", "Name <real@example.com>", "Reply-To:\r\n Name <real@example.com>\r\n"
    )
