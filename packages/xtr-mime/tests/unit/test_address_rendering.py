"""An address as a header writes it: the domain in ASCII, the name read back unchanged."""

from __future__ import annotations

from email.header import decode_header

import pytest

from tests.support.address_reading import read_address, read_name
from xtr_mime import Address
from xtr_mime._engine import Mailbox, header_body
from xtr_mime.exception import RfcComplianceError


def test_has_unicode_localpart_is_true_only_for_a_non_ascii_local_part() -> None:
    # "dømi" means "example" and is reserved by the .fo registry.
    assert not Address("info@dømi.fo").has_unicode_localpart()
    assert Address("dømi@dømi.fo").has_unicode_localpart()


@pytest.mark.parametrize("name", ["", " ", " \r\n "])
def test_a_blank_name_renders_the_address_alone(name: str) -> None:
    assert Address("mail@example.org", name).to_string() == "mail@example.org"


def test_a_name_with_a_comma_and_a_quote_reads_back_unchanged() -> None:
    address = Address("fabien@example.com", 'Fabien, "Potencier')

    assert read_address(address.to_string()) == ('Fabien, "Potencier', "fabien@example.com")


@pytest.mark.parametrize("name", ['Fabien \\ "Potencier', "Fabien\\"])
def test_a_name_with_backslashes_reads_back_unchanged(name: str) -> None:
    address = Address("fabien@example.com", name)

    assert read_address(address.to_string()) == (name, "fabien@example.com")


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("Fabien \udcb1 Potencier", id="plain"),
        pytest.param("Fabien \udcb1 \\ Potencier", id="quoted"),
    ],
)
def test_a_name_holding_a_lone_surrogate_is_refused(name: str) -> None:
    # A str cannot hold invalid UTF-8: a byte that failed to decode survives as a lone
    # surrogate, which is not text, and which some Python versions cannot write when quoted.
    with pytest.raises(RfcComplianceError, match="surrogate"):
        _ = Address("fabien@example.com", name)


def test_get_encoded_address_writes_an_international_domain_in_punycode() -> None:
    assert Address("test@fußball.test").get_encoded_address() == "test@xn--fuball-cta.test"
    assert Address("info@dømi.fo").get_encoded_address() == "info@xn--dmi-0na.fo"


def test_get_encoded_address_leaves_an_ascii_address_alone() -> None:
    assert Address("Fabien@Example.COM").get_encoded_address() == "Fabien@Example.COM"


def test_a_domain_that_is_not_a_valid_international_name_is_refused() -> None:
    with pytest.raises(RfcComplianceError):
        _ = Address("user@ab--cé.com")


# "user" is settled by the quick check for common addresses, "o'b" by the full grammar.
@pytest.mark.parametrize("local_part", ["user", "o'b"])
@pytest.mark.parametrize(
    "domain",
    [
        pytest.param("ab--cd.com", id="hyphens-in-third-and-fourth-place"),
        pytest.param("xn--abc.com", id="invalid-a-label"),
    ],
)
def test_a_domain_is_refused_whatever_the_local_part(local_part: str, domain: str) -> None:
    with pytest.raises(RfcComplianceError):
        _ = Address(f"{local_part}@{domain}")


@pytest.mark.parametrize("local_part", ["user", "o'b"])
def test_an_a_label_domain_is_accepted_whatever_the_local_part(local_part: str) -> None:
    value = f"{local_part}@xn--exmple-cua.com"

    assert Address(value).get_address() == value


def test_a_name_outside_ascii_reads_back_unchanged() -> None:
    address = Address.create("Žluťoučký Kůň <alice@dømi.fo>")

    assert read_address(address.to_string()) == ("Žluťoučký Kůň", "alice@xn--dmi-0na.fo")
    assert read_name(address.get_encoded_name()) == "Žluťoučký Kůň"
    assert address.get_encoded_name().isascii()


def test_get_encoded_name_is_empty_without_a_name() -> None:
    assert Address("fabien@example.com").get_encoded_name() == ""


def test_a_long_name_renders_on_one_line() -> None:
    name = ("Žluťoučký kůň úpěl ďábelské ódy " * 4).strip()
    address = Address("fabien@example.com", name)

    rendered = address.to_string()

    assert "\r" not in rendered
    assert "\n" not in rendered
    # Read as RFC 2047 says: whitespace between two encoded words is dropped, so a space
    # between two words of the name must be written inside an encoded word.
    parts: list[tuple[bytes | str, str | None]] = decode_header(rendered)
    decoded = "".join(
        part.decode(charset or "ascii") if isinstance(part, bytes) else part
        for part, charset in parts
    )
    assert decoded == f"{name} <fabien@example.com>"


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\x85"])
def test_a_name_holding_a_line_separator_cannot_be_rendered(separator: str) -> None:
    address = Address("dømi@dømi.fo", f"Dømi{separator}Bcc: evil@attacker.com")

    with pytest.raises(RfcComplianceError, match="control character"):
        _ = address.to_string()


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
    assert read_name(address.get_encoded_name()) == "Dømi"


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
