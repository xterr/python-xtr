"""Addresses as the engine takes them: punycoded domains, literal names, checked local parts."""

from __future__ import annotations

import pytest

from tests.support.engine_cases import CONTROL_CHARACTERS, ENCODED_WORD_NAME, SEPARATORS
from xtr_mime import _engine
from xtr_mime._engine import Mailbox, MailboxGroup
from xtr_mime.exception import RfcComplianceError


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


@pytest.mark.parametrize("name", ["=?utf-8?q?hello?=", "Hi =?utf-8?b?aGk=?= there"])
def test_a_display_name_holding_an_encoded_word_is_refused(name: str) -> None:
    with pytest.raises(RfcComplianceError, match="literal"):
        _ = _engine.fold_header("To", [Mailbox(name, "real@example.com")])


def test_a_group_name_holding_an_encoded_word_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="literal"):
        _ = _engine.fold_header("To", [MailboxGroup("=?utf-8?q?hello?=", ())])


def test_a_long_display_name_holding_an_encoded_word_is_shown_cut() -> None:
    name = "=?utf-8?q?x?= " + "x" * 980

    with pytest.raises(RfcComplianceError) as raised:
        _ = _engine.fold_header("Cc", [Mailbox(name, "real@example.com")])

    assert str(raised.value) == (
        f'The display name "{name[:64]}…" holds an encoded word: a reader would show it '
        "decoded, not as the literal text it is."
    )


@pytest.mark.parametrize("address", ["dø mi@example.com", "dø@mi@example.com", "dø."])
def test_a_non_ascii_local_part_the_engine_cannot_parse_is_refused(address: str) -> None:
    with pytest.raises(RfcComplianceError, match="email address"):
        _ = _engine.fold_header("To", [Mailbox("", address)])
