"""An address is checked when built, keeps what it was given and renders through the engine.

Rendered values are read back the way a mail client reads them and compared decoded: which
encoded-word form the engine picks is its business, not this class's.
"""

from __future__ import annotations

from email import policy as stdlib_policy
from email.header import decode_header, make_header
from email.headerregistry import AddressHeader, BaseHeader
from typing import cast

import pytest

from xtr_mime import Address
from xtr_mime._engine import Mailbox, header_body
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError


def _read(rendered: str) -> tuple[str, str]:
    """Read a rendered address back into its decoded display name and its address."""
    header = cast("BaseHeader", stdlib_policy.default.header_factory("To", rendered))
    assert isinstance(header, AddressHeader)
    (mailbox,) = header.addresses
    return mailbox.display_name, f"{mailbox.username}@{mailbox.domain}"


def _read_name(encoded_name: str) -> str:
    return _read(f"{encoded_name} <someone@example.com>")[0]


def test_an_international_domain_is_kept_and_rendered_in_ascii() -> None:
    address = Address("fabien@exämple.com")

    assert address.get_address() == "fabien@exämple.com"
    assert address.to_string() == "fabien@xn--exmple-cua.com"
    assert address.get_encoded_address() == "fabien@xn--exmple-cua.com"


def test_a_named_address_renders_the_name_before_the_ascii_address() -> None:
    address = Address("fabien@exämple.com", "Fabien")

    assert address.get_name() == "Fabien"
    assert address.get_address() == "fabien@exämple.com"
    assert _read(address.to_string()) == ("Fabien", "fabien@xn--exmple-cua.com")
    assert address.get_encoded_address() == "fabien@xn--exmple-cua.com"


def test_an_address_with_spaces_in_the_local_part_is_refused() -> None:
    with pytest.raises(RfcComplianceError):
        _ = Address("fab   pot@example.com")


@pytest.mark.parametrize(
    "value",
    [
        "user@example.com",
        "first.last+tag@mail.example.co.uk",
        "o_k-1@a-b.io",
        "0123456789abcdef0123456789abcdef@example.com",
        "o'brien@example.com",
        "user@localhost",
        "user@[127.0.0.1]",
    ],
)
def test_a_valid_address_is_kept_as_given(value: str) -> None:
    assert Address(value).get_address() == value


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


def test_an_unquoted_at_sign_in_the_local_part_is_refused_naming_the_address() -> None:
    with pytest.raises(RfcComplianceError) as caught:
        _ = Address("em@il@example.test")

    assert (
        str(caught.value)
        == 'Email "em@il@example.test" does not comply with addr-spec of RFC 5322.'
    )


def test_a_quoted_at_sign_in_the_local_part_is_accepted() -> None:
    assert Address('"em@il"@example.test').get_address() == '"em@il"@example.test'


def test_an_at_sign_in_a_domain_literal_is_accepted() -> None:
    assert Address("user@[em@il]").get_address() == "user@[em@il]"


def test_an_unquoted_at_sign_in_the_local_part_before_a_domain_literal_is_refused() -> None:
    with pytest.raises(RfcComplianceError):
        _ = Address("em@il@[example]")


def test_quoted_at_signs_in_both_the_local_part_and_a_domain_literal_are_accepted() -> None:
    assert Address('"em@il"@[em@il]').get_address() == '"em@il"@[em@il]'


def test_a_comment_after_a_domain_literal_is_accepted_and_kept() -> None:
    assert Address("user@[em@il] (comment)").get_address() == "user@[em@il] (comment)"


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
    assert _read(address.to_string()) == ("ab", "fabien@example.com")


def test_a_tab_the_one_control_character_a_phrase_allows_stays_in_the_name() -> None:
    assert Address("fabien@example.com", "Jean\tDupont").get_name() == "Jean\tDupont"


def test_the_address_and_the_name_are_trimmed() -> None:
    address = Address("  fabien@example.com\n", " \tFabien \r\n")

    assert (address.get_address(), address.get_name()) == ("fabien@example.com", "Fabien")


def test_create_returns_an_address_it_is_given_as_is() -> None:
    fabien = Address("fabien@example.com")
    helene = Address("helene@example.com", "Helene")

    assert Address.create(fabien) is fabien
    assert Address.create(helene) is helene
    assert Address.create("fabien@example.com") == fabien


def test_create_refuses_a_string_it_cannot_parse() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Address.create("<fabien@example")

    assert (
        str(caught.value) == 'Could not parse "<fabien@example" to an "xtr_mime.Address" instance.'
    )


@pytest.mark.parametrize(
    ("value", "name", "address"),
    [
        ("example@example.com", "", "example@example.com"),
        ("<example@example.com>", "", "example@example.com"),
        ("Jane Doe <example@example.com>", "Jane Doe", "example@example.com"),
        ("Jane Doe<example@example.com>", "Jane Doe", "example@example.com"),
        ("'Jane Doe' <example@example.com>", "Jane Doe", "example@example.com"),
        ('"Jane Doe" <example@example.com>', "Jane Doe", "example@example.com"),
        ('Jane Doe <"ex<ample"@example.com>', "Jane Doe", '"ex<ample"@example.com'),
        ('Jane Doe <"ex<amp>le"@example.com>', "Jane Doe", '"ex<amp>le"@example.com'),
        ('Jane Doe > <"ex<am  p>le"@example.com>', "Jane Doe >", '"ex<am  p>le"@example.com'),
        ("Jane Doe <example@example.com>discarded", "Jane Doe", "example@example.com"),
    ],
)
def test_create_parses_a_name_and_an_address_and_reads_its_own_rendering_back(
    value: str, name: str, address: str
) -> None:
    created = Address.create(value)
    read_back = Address.create(created.to_string())

    assert (created.get_name(), created.get_address()) == (name, address)
    assert (read_back.get_name(), read_back.get_address()) == (name, address)


def test_create_refuses_a_value_that_is_neither_an_address_nor_a_string() -> None:
    with pytest.raises(TypeError):
        _ = Address.create(cast("str", object()))


def test_create_array_creates_every_address_in_order() -> None:
    fabien = Address("fabien@example.com")
    helene = Address("helene@example.com", "Helene")

    created = Address.create_array([fabien, helene])

    assert created[0] is fabien
    assert created[1] is helene
    assert Address.create_array(["fabien@example.com"]) == [fabien]


def test_create_array_refuses_a_value_that_is_neither_an_address_nor_a_string() -> None:
    with pytest.raises(TypeError):
        _ = Address.create_array([cast("str", object())])


def test_has_unicode_localpart_is_true_only_for_a_non_ascii_local_part() -> None:
    # "dømi" means "example" and is reserved by the .fo registry.
    assert not Address("info@dømi.fo").has_unicode_localpart()
    assert Address("dømi@dømi.fo").has_unicode_localpart()


@pytest.mark.parametrize("name", ["", " ", " \r\n "])
def test_a_blank_name_renders_the_address_alone(name: str) -> None:
    assert Address("mail@example.org", name).to_string() == "mail@example.org"


def test_a_name_with_a_comma_and_a_quote_reads_back_unchanged() -> None:
    address = Address("fabien@example.com", 'Fabien, "Potencier')

    assert _read(address.to_string()) == ('Fabien, "Potencier', "fabien@example.com")


@pytest.mark.parametrize("name", ['Fabien \\ "Potencier', "Fabien\\"])
def test_a_name_with_backslashes_reads_back_unchanged(name: str) -> None:
    address = Address("fabien@example.com", name)

    assert _read(address.to_string()) == (name, "fabien@example.com")


def test_a_name_holding_undecodable_bytes_reads_back_unchanged() -> None:
    # A str cannot hold invalid UTF-8; a byte that failed to decode survives as a lone surrogate.
    name = "Fabien \udcb1 \\ Potencier"
    address = Address("fabien@example.com", name)

    assert _read(address.to_string()) == (name, "fabien@example.com")


def test_get_encoded_address_writes_an_international_domain_in_punycode() -> None:
    assert Address("test@fußball.test").get_encoded_address() == "test@xn--fuball-cta.test"
    assert Address("info@dømi.fo").get_encoded_address() == "info@xn--dmi-0na.fo"


def test_get_encoded_address_leaves_an_ascii_address_alone() -> None:
    assert Address("Fabien@Example.COM").get_encoded_address() == "Fabien@Example.COM"


def test_a_domain_that_is_not_a_valid_international_name_is_refused() -> None:
    with pytest.raises(RfcComplianceError):
        _ = Address("user@ab--cé.com")


def test_a_name_outside_ascii_reads_back_unchanged() -> None:
    address = Address.create("Žluťoučký Kůň <alice@dømi.fo>")

    assert _read(address.to_string()) == ("Žluťoučký Kůň", "alice@xn--dmi-0na.fo")
    assert _read_name(address.get_encoded_name()) == "Žluťoučký Kůň"
    assert address.get_encoded_name().isascii()


def test_get_encoded_name_is_empty_without_a_name() -> None:
    assert Address("fabien@example.com").get_encoded_name() == ""


def test_a_long_name_renders_on_one_line() -> None:
    name = ("Žluťoučký kůň úpěl ďábelské ódy " * 4).strip()
    address = Address("fabien@example.com", name)

    rendered = address.to_string()

    assert "\r" not in rendered
    assert "\n" not in rendered
    # Read with the RFC 2047 decoder: the header parser keeps the space between two encoded
    # words, which the RFC says a reader drops.
    assert str(make_header(decode_header(rendered))) == f"{name} <fabien@example.com>"


def test_to_string_is_what_the_engine_writes_for_an_ascii_local_part() -> None:
    address = Address("alice@dømi.fo", "Alice, Liddell")

    expected = header_body("To", [Mailbox("Alice, Liddell", "alice@dømi.fo")])

    assert address.to_string() == expected
    assert str(address) == expected


def test_a_unicode_local_part_renders_as_is_for_an_smtputf8_session() -> None:
    address = Address("dømi@dømi.fo", "Dømi")

    assert Address("dømi@dømi.fo").to_string() == "dømi@xn--dmi-0na.fo"
    # The whole header is raw UTF-8 then, so the name is too.
    assert address.to_string() == "Dømi <dømi@xn--dmi-0na.fo>"
    assert _read_name(address.get_encoded_name()) == "Dømi"


def test_a_name_holding_an_encoded_word_cannot_be_rendered() -> None:
    address = Address("real@example.com", "=?utf-8?q?evil=40attacker.com?=")

    with pytest.raises(RfcComplianceError, match="literal"):
        _ = address.to_string()


def test_addresses_with_the_same_address_and_name_are_equal() -> None:
    assert Address("a@example.com", "A") == Address("a@example.com", "A")
    assert hash(Address("a@example.com", "A")) == hash(Address("a@example.com", "A"))
    assert Address("a@example.com", "A") != Address("a@example.com", "B")
    assert Address("a@example.com") != Address("b@example.com")
    assert Address("a@example.com") != "a@example.com"


def test_repr_names_the_address_and_the_name() -> None:
    assert repr(Address("a@example.com", "A")) == "Address('a@example.com', 'A')"
