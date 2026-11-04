from __future__ import annotations

import pytest

from tests.support.wire import decode_addresses, decode_words
from xtr_mime import Address
from xtr_mime.exception import InvalidArgumentError
from xtr_mime.header import MailboxHeader


def test_the_constructor_keeps_the_address() -> None:
    address = Address("fabien@example.com")
    header = MailboxHeader("Sender", address)

    assert header.get_address() is address
    assert header.get_body() is address


def test_the_address_can_be_replaced() -> None:
    header = MailboxHeader("Sender", Address("fabien@example.com"))
    address = Address("helene@example.com")

    header.set_body(address)
    assert header.get_address() is address
    assert header.get_body() is address

    address = Address("thomas@example.com")
    header.set_address(address)
    assert header.get_address() is address
    assert header.get_body() is address


def test_set_body_refuses_what_is_not_an_address() -> None:
    header = MailboxHeader("Sender", Address("fabien@example.com"))

    with pytest.raises(InvalidArgumentError):
        header.set_body("helene@example.com")


def test_a_bare_address_is_the_body() -> None:
    header = MailboxHeader("Sender", Address("fabien@example.com"))

    assert header.get_body_as_string() == "fabien@example.com"


def test_an_international_domain_is_idn_encoded() -> None:
    header = MailboxHeader("Sender", Address("fabien@exämple.com"))

    assert header.get_body_as_string() == "fabien@xn--exmple-cua.com"


def test_a_name_goes_before_the_address() -> None:
    header = MailboxHeader("Sender", Address("fabien@example.com", "Fabien Potencier"))

    assert header.get_body_as_string() == "Fabien Potencier <fabien@example.com>"


def test_quotes_in_the_name_are_escaped_in_a_quoted_string() -> None:
    address = Address("fabien@example.com", 'Fabien Potencier, "from Example"')

    body = MailboxHeader("Sender", address).get_body_as_string()

    assert body == '"Fabien Potencier, \\"from Example\\"" <fabien@example.com>'


def test_backslashes_in_the_name_are_escaped_in_a_quoted_string() -> None:
    address = Address("fabien@example.com", "Fabien Potencier, \\escaped\\")

    body = MailboxHeader("From", address).get_body_as_string()

    assert body == '"Fabien Potencier, \\\\escaped\\\\" <fabien@example.com>'


def test_a_non_ascii_name_is_encoded() -> None:
    # Adapted: upstream's iso-8859-1 byte 0x8F is a C1 control as a character, refused here.
    header = MailboxHeader("Sender", Address("fabien@example.com", "Fabien P\xf8tencier"))
    header.set_charset("iso-8859-1")

    rendered = header.to_string()

    # Adapted (D1): decode and compare; the engine writes UTF-8 whatever charset is set.
    assert rendered.isascii()
    assert decode_addresses(rendered) == [("Fabien P\xf8tencier", "fabien@example.com")]


def test_utf8_characters_in_the_local_part_are_written_raw() -> None:
    header = MailboxHeader("Sender", Address("fabïen@example.com"))

    assert header.get_body_as_string() == "fabïen@example.com"


@pytest.mark.parametrize("name", ["Fabïen Pötencier", "Fabïen  Pötencier"])
def test_a_name_next_to_a_utf8_local_part_is_written_raw(name: str) -> None:
    rendered = MailboxHeader("Sender", Address("fabïen@example.com", name)).to_string()

    # Adapted (D1): with a UTF-8 local part the engine writes the whole field in raw UTF-8
    # (RFC 6532) rather than as encoded words, spaces included.
    assert rendered == f"Sender: {name} <fabïen@example.com>"


@pytest.mark.parametrize("address", ["fabïen@example.com", "fabien@example.com"])
@pytest.mark.parametrize(
    "name",
    [
        "Fabïen  Pötencier  Länge",
        "Fabïen   Pötencier",
        "Fabïen  Pötencier and  Länge  Grüße",
    ],
)
def test_spaces_between_encoded_words_are_not_dropped(address: str, name: str) -> None:
    rendered = MailboxHeader("Sender", Address(address, name)).to_string()

    # Adapted (D1): decode the encoded words and compare instead of the Q bytes.
    assert decode_words(rendered) == f"{name} <{address}>"


def test_to_string() -> None:
    assert MailboxHeader("Sender", Address("fabien@example.com")).to_string() == (
        "Sender: fabien@example.com"
    )
    assert MailboxHeader(
        "Sender", Address("fabien@example.com", "Fabien Potencier")
    ).to_string() == ("Sender: Fabien Potencier <fabien@example.com>")
