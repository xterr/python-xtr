"""An address is checked when built, keeps what it was given and renders through the engine.

Rendered values are read back the way a mail client reads them and compared decoded: which
encoded-word form the engine picks is its business, not this class's. Parsing a string into
an address is tested in ``test_address_create.py``, rendering in ``test_address_rendering.py``.
"""

from __future__ import annotations

import pytest

from tests.support.address_reading import UNSAFE_IN_A_MESSAGE, read_address
from xtr_mime import Address
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError

_VALID_ADDRESSES = (
    "user@example.com",
    "first.last+tag@mail.example.co.uk",
    "o_k-1@a-b.io",
    "0123456789abcdef0123456789abcdef@example.com",
    "o'brien@example.com",
    "user@localhost",
    "user@[127.0.0.1]",
    "user@[IPv6:2001:db8::1]",
    "user@[x-tag:em@il]",
)

# Every address the tests here build: an address that builds must render too.
_ACCEPTED_ADDRESSES = (
    *_VALID_ADDRESSES,
    "fabien@exämple.com",
    "fabien@example.com",
    "helene@example.com",
    "example@example.com",
    "mail@example.org",
    "real@example.com",
    "a@example.com",
    "b@example.com",
    "Fabien@Example.COM",
    '"em@il"@example.test',
    '"em@il"@[x-tag:em@il]',
    "user@[192.0.2.1] (comment)",
    '"ex<ample"@example.com',
    '"ex<amp>le"@example.com',
    '"ex<am  p>le"@example.com',
    "info@dømi.fo",
    "dømi@dømi.fo",
    "alice@dømi.fo",
    "test@fußball.test",
    "user@xn--exmple-cua.com",
    "o'b@xn--exmple-cua.com",
)


def test_an_international_domain_is_kept_and_rendered_in_ascii() -> None:
    address = Address("fabien@exämple.com")

    assert address.get_address() == "fabien@exämple.com"
    assert address.to_string() == "fabien@xn--exmple-cua.com"
    assert address.get_encoded_address() == "fabien@xn--exmple-cua.com"


def test_a_named_address_renders_the_name_before_the_ascii_address() -> None:
    address = Address("fabien@exämple.com", "Fabien")

    assert address.get_name() == "Fabien"
    assert address.get_address() == "fabien@exämple.com"
    assert read_address(address.to_string()) == ("Fabien", "fabien@xn--exmple-cua.com")
    assert address.get_encoded_address() == "fabien@xn--exmple-cua.com"


def test_an_address_with_spaces_in_the_local_part_is_refused() -> None:
    with pytest.raises(RfcComplianceError):
        _ = Address("fab   pot@example.com")


@pytest.mark.parametrize("value", _VALID_ADDRESSES)
def test_a_valid_address_is_kept_as_given(value: str) -> None:
    assert Address(value).get_address() == value


@pytest.mark.parametrize("value", _ACCEPTED_ADDRESSES)
def test_every_accepted_address_renders(value: str) -> None:
    address = Address(value, "Jane Doe")

    rendered = address.to_string()
    encoded = address.get_encoded_address()

    assert read_address(rendered) == ("Jane Doe", read_address(encoded)[1])


@pytest.mark.parametrize(
    "value",
    [
        "a..b@example.com",
        ".a@example.com",
        "a.@example.com",
        "a@-example.com",
        "a@example-.com",
        "a@example..com",
        "a@.example.com",
        "a@example.com.",
        "@example.com",
        "a@",
        "no-at-sign.example.com",
        "a@[example",
        "a@exa_mple.com",
    ],
)
def test_an_invalid_address_is_refused(value: str) -> None:
    with pytest.raises(RfcComplianceError):
        _ = Address(value)


@pytest.mark.parametrize(
    "full_stop",
    [
        pytest.param(".", id="full-stop"),
        pytest.param("\u3002", id="ideographic-full-stop"),
        pytest.param("\uff0e", id="fullwidth-full-stop"),
        pytest.param("\uff61", id="halfwidth-ideographic-full-stop"),
    ],
)
def test_a_domain_ending_in_any_full_stop_is_refused(full_stop: str) -> None:
    # IDNA reads all four as the dot between two labels, and a final one as the DNS root.
    with pytest.raises(RfcComplianceError):
        _ = Address(f"user@example.com{full_stop}")


def test_an_unquoted_at_sign_in_the_local_part_is_refused_naming_the_address() -> None:
    with pytest.raises(RfcComplianceError) as caught:
        _ = Address("em@il@example.test")

    assert (
        str(caught.value)
        == 'Email "em@il@example.test" does not comply with addr-spec of RFC 5322.'
    )


@pytest.mark.parametrize(
    ("address", "shown"),
    [
        ("em\udc80il@example.test", "em\\udc80il"),
        ("a\u2028b@example.test", "a\\u2028b"),
        ("a\x85b@example.test", "a\\x85b"),
    ],
)
def test_an_invalid_address_is_named_escaped_in_the_error(address: str, shown: str) -> None:
    with pytest.raises(RfcComplianceError) as caught:
        _ = Address(address)

    message = str(caught.value)
    assert message == f'Email "{shown}@example.test" does not comply with addr-spec of RFC 5322.'
    assert not any(character in message for character in UNSAFE_IN_A_MESSAGE)


def test_a_quoted_at_sign_in_the_local_part_is_accepted() -> None:
    assert Address('"em@il"@example.test').get_address() == '"em@il"@example.test'


def test_a_long_invalid_address_is_shown_cut_to_its_first_64_characters() -> None:
    with pytest.raises(RfcComplianceError) as caught:
        _ = Address("a" * 10_000 + "@@example.test")

    assert str(caught.value) == (f'Email "{"a" * 64}…" does not comply with addr-spec of RFC 5322.')


def test_a_long_address_that_does_not_parse_is_shown_cut_to_its_first_64_characters() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Address.create("<" + "a" * 10_000)

    assert str(caught.value) == (
        f'Could not parse "<{"a" * 63}…" to an "xtr_mime.Address" instance.'
    )


def test_an_at_sign_in_a_general_address_literal_is_accepted() -> None:
    assert Address("user@[x-tag:em@il]").get_address() == "user@[x-tag:em@il]"


def test_an_unquoted_at_sign_in_the_local_part_before_a_domain_literal_is_refused() -> None:
    with pytest.raises(RfcComplianceError):
        _ = Address("em@il@[x-tag:example]")


def test_quoted_at_signs_in_both_the_local_part_and_a_domain_literal_are_accepted() -> None:
    assert Address('"em@il"@[x-tag:em@il]').get_address() == '"em@il"@[x-tag:em@il]'


@pytest.mark.parametrize(
    "literal",
    [
        "[em@il]",
        "[example]",
        "[x>,evil@attacker.com,<y]",
        "[x:a,b]",
        "[x:a<b]",
        "[x:a;b]",
        '[x:a"b]',
        "[x:a(b)]",
        "[x:]",
        "[-x:a]",
        "[x-:a]",
        "[256.1.1.1]",
        "[1.2.3]",
        "[01.2.3.4]",
        "[IPv6:zz::1]",
        "[IPv6:fe80::1%eth0]",
        "[IPv6:1.2.3.4]",
        "[]",
    ],
)
def test_a_domain_literal_that_is_not_an_rfc_5321_address_literal_is_refused(literal: str) -> None:
    with pytest.raises(RfcComplianceError):
        _ = Address(f"user@{literal}")


@pytest.mark.parametrize(
    "literal",
    [
        "[192.0.2.1]",
        "[0.0.0.0]",
        "[IPv6:2001:db8::1]",
        "[ipv6:::1]",
        "[IPv6:::ffff:192.0.2.1]",
        "[x-tag:a.b-c_d=e?f@g]",
    ],
)
def test_an_rfc_5321_address_literal_is_accepted(literal: str) -> None:
    assert Address(f"user@{literal}").get_address() == f"user@{literal}"


def test_a_comment_after_a_domain_literal_is_accepted_and_kept() -> None:
    assert Address("user@[192.0.2.1] (comment)").get_address() == "user@[192.0.2.1] (comment)"


def test_a_comment_after_a_domain_literal_stays_out_of_the_encoded_address() -> None:
    """The encoded address is what an SMTP envelope carries, where a comment has no place."""
    address = Address("user@[192.0.2.1] (comment)", "Jane")

    assert address.get_encoded_address() == "user@[192.0.2.1]"
    assert "comment" not in address.to_string()
    assert read_address(address.to_string()) == ("Jane", "user@[192.0.2.1]")


def test_a_comment_after_a_domain_literal_outside_printable_ascii_is_refused() -> None:
    with pytest.raises(RfcComplianceError):
        _ = Address("user@[1.2.3.4] (ü)")


@pytest.mark.parametrize(
    "value",
    [
        pytest.param('"x\r\nBcc: attacker@evil"@example.com', id="crlf-in-quoted-string"),
        pytest.param("foo\r@example.com", id="cr"),
        pytest.param("foo\n@example.com", id="lf"),
        pytest.param("foo\x00@example.com", id="nul"),
        pytest.param("foo\t@example.com", id="htab"),
        pytest.param("foo\x7f@example.com", id="del"),
        pytest.param("foo@example\x01.com", id="control-in-domain"),
    ],
)
def test_control_characters_in_an_address_are_refused(value: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Address(value)

    assert str(caught.value) == "Email address contains control characters."
    assert type(caught.value) is InvalidArgumentError


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("a\x00b", id="nul"),
        pytest.param("a\x01b", id="soh"),
        pytest.param("a\nb", id="lf"),
        pytest.param("a\rb", id="cr"),
        pytest.param("a\x0bb", id="vt"),
        pytest.param("a\x1fb", id="us"),
        pytest.param("a\x7fb", id="del"),
    ],
)
def test_control_characters_are_stripped_from_the_name(name: str) -> None:
    address = Address("fabien@example.com", name)

    assert address.get_name() == "ab"
    assert read_address(address.to_string()) == ("ab", "fabien@example.com")


def test_a_tab_the_one_control_character_a_phrase_allows_stays_in_the_name() -> None:
    assert Address("fabien@example.com", "Jean\tDupont").get_name() == "Jean\tDupont"


def test_the_address_and_the_name_are_trimmed() -> None:
    address = Address("  fabien@example.com\n", " \tFabien \r\n")

    assert (address.get_address(), address.get_name()) == ("fabien@example.com", "Fabien")
