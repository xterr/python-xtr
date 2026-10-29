from __future__ import annotations

import pytest

from tests.support.wire import assert_folded, decode, decode_addresses, decode_words
from xtr_mime import Address, Group
from xtr_mime.exception import InvalidArgumentError
from xtr_mime.header import MailboxListHeader


def test_a_mailbox_is_set_for_an_address() -> None:
    header = MailboxListHeader("From", [Address("chris@example.org")])

    assert header.get_address_strings() == ["chris@example.org"]


def test_a_mailbox_is_rendered_for_a_name_and_address() -> None:
    header = MailboxListHeader("From", [Address("chris@example.org", "Chris Corbyn")])

    assert header.get_address_strings() == ["Chris Corbyn <chris@example.org>"]


def test_the_address_can_be_returned() -> None:
    addresses = [Address("chris@example.org")]

    assert MailboxListHeader("From", addresses).get_addresses() == addresses


def test_quotes_in_the_name_are_quoted() -> None:
    header = MailboxListHeader("From", [Address("chris@example.org", 'Chris Corbyn, "DHE"')])

    assert header.get_address_strings() == ['"Chris Corbyn, \\"DHE\\"" <chris@example.org>']


def test_escape_characters_in_the_name_are_quoted() -> None:
    address = Address("chris@example.org", "Chris Corbyn, \\escaped\\")

    strings = MailboxListHeader("From", [address]).get_address_strings()

    assert strings == ['"Chris Corbyn, \\\\escaped\\\\" <chris@example.org>']


def test_parentheses_in_the_name_are_quoted() -> None:
    header = MailboxListHeader("From", [Address("j.doe@example.com", "J Doe (ACME)")])

    assert header.get_address_strings() == ['"J Doe (ACME)" <j.doe@example.com>']


def test_utf8_characters_in_the_domain_are_idn_encoded() -> None:
    header = MailboxListHeader("From", [Address("chris@swïftmailer.org", "Chris Corbyn")])

    assert header.get_address_strings() == ["Chris Corbyn <chris@xn--swftmailer-78a.org>"]


def test_utf8_characters_in_the_local_part_are_written_raw() -> None:
    header = MailboxListHeader("From", [Address("chrïs@example.org", "Chris Corbyn")])

    assert header.get_address_strings() == ["Chris Corbyn <chrïs@example.org>"]


def test_get_addresses_returns_the_addresses_with_their_names() -> None:
    addresses = [Address("chris@example.org", "Chris Corbyn, DHE")]

    assert MailboxListHeader("From", addresses).get_addresses() == addresses


def test_multiple_addresses_as_mailbox_strings() -> None:
    addresses = [Address("chris@example.org"), Address("mark@example.org")]

    strings = MailboxListHeader("From", addresses).get_address_strings()

    assert strings == ["chris@example.org", "mark@example.org"]


def test_a_non_ascii_name_is_encoded() -> None:
    # Adapted: upstream's iso-8859-1 byte 0x8F is a C1 control as a character, refused here.
    header = MailboxListHeader("From", [Address("chris@example.org", "Chris C\xf8rbyn")])
    header.set_charset("iso-8859-1")

    (string,) = header.get_address_strings()

    # Adapted (D1): decode and compare; the engine writes UTF-8 whatever charset is set.
    assert string.isascii()
    assert decode_addresses(f"From: {string}") == [("Chris C\xf8rbyn", "chris@example.org")]


def test_encoding_line_length_calculations() -> None:
    name = "Chris C\xf8rbyn " * 8
    header = MailboxListHeader("From", [Address("chris@example.org", name)])

    rendered = header.to_string()

    # Adapted (D1): a name long enough to fold, then the folding rules and the name read back.
    assert_folded(rendered)
    assert decode_words(rendered) == f"{name.strip()} <chris@example.org>"


def test_the_body_is_the_mailbox_string() -> None:
    header = MailboxListHeader("From", [Address("chris@example.org", "Chris Corbyn")])

    assert header.get_body_as_string() == "Chris Corbyn <chris@example.org>"


def test_the_body_joins_multiple_mailboxes() -> None:
    header = MailboxListHeader(
        "From",
        [
            Address("chris@example.org", "Chris Corbyn"),
            Address("mark@example.org", "Mark Corbyn"),
        ],
    )

    assert header.get_body_as_string() == (
        "Chris Corbyn <chris@example.org>, Mark Corbyn <mark@example.org>"
    )


def test_set_body() -> None:
    header = MailboxListHeader("From", [])
    addresses = [Address("chris@example.org")]

    header.set_body(addresses)

    assert header.get_addresses() == addresses


def test_set_body_refuses_what_is_not_a_list_of_addresses() -> None:
    header = MailboxListHeader("From", [])

    with pytest.raises(InvalidArgumentError):
        header.set_body("chris@example.org")
    with pytest.raises(InvalidArgumentError):
        header.set_body(["chris@example.org"])


def test_get_body() -> None:
    addresses = [Address("chris@example.org")]

    assert MailboxListHeader("From", addresses).get_body() == addresses


def test_an_empty_list_has_an_empty_body() -> None:
    assert MailboxListHeader("From", []).get_body_as_string() == ""


def test_to_string() -> None:
    header = MailboxListHeader(
        "From",
        [
            Address("chris@example.org", "Chris Corbyn"),
            Address("mark@example.org", "Mark Corbyn"),
        ],
    )

    assert header.to_string() == (
        "From: Chris Corbyn <chris@example.org>, Mark Corbyn <mark@example.org>"
    )


def test_to_string_never_emits_control_characters_from_the_name() -> None:
    header = MailboxListHeader("To", [Address("chris@example.org", "Chris\x00Corbyn")])

    assert header.to_string() == "To: ChrisCorbyn <chris@example.org>"


def test_to_string_with_a_group() -> None:
    group = Group(
        "Friends", [Address("chris@example.org"), Address("mark@example.org", "Mark Corbyn")]
    )

    assert MailboxListHeader("To", [group]).to_string() == (
        "To: Friends: chris@example.org, Mark Corbyn <mark@example.org>;"
    )


def test_to_string_with_an_empty_group() -> None:
    header = MailboxListHeader("To", [Group("undisclosed-recipients")])

    assert header.to_string() == "To: undisclosed-recipients:;"
    assert header.get_address_strings() == ["undisclosed-recipients:;"]


def test_to_string_with_a_group_and_a_mailbox() -> None:
    header = MailboxListHeader(
        "To", [Address("chris@example.org"), Group("Friends", [Address("mark@example.org")])]
    )

    assert header.to_string() == "To: chris@example.org, Friends: mark@example.org;"


def test_a_non_ascii_group_name_is_encoded() -> None:
    header = MailboxListHeader("To", [Group("Câlins", [Address("chris@example.org")])])

    rendered = header.to_string()

    # Adapted (D1): decode and compare instead of the Q bytes.
    assert rendered.isascii()
    assert decode(rendered) == "Câlins: chris@example.org;"


def test_a_group_name_holding_a_colon_or_semicolon_is_quoted() -> None:
    header = MailboxListHeader("To", [Group("a:b;c", [Address("chris@example.org")])])

    assert header.to_string() == 'To: "a:b;c": chris@example.org;'


def test_get_addresses_flattens_groups() -> None:
    chris = Address("chris@example.org")
    mark = Address("mark@example.org")
    friends = Group("Friends", [mark])
    undisclosed = Group("undisclosed-recipients")

    header = MailboxListHeader("To", [chris, friends, undisclosed])

    assert header.get_addresses() == [chris, mark]
    assert header.get_body() == [chris, mark]
    assert header.get_address_list() == [chris, friends, undisclosed]


def test_create_address_list() -> None:
    mark = Address("mark@example.org")
    friends = Group("Friends")

    address_list = MailboxListHeader.create_address_list(["chris@example.org", mark, friends])

    assert address_list == [Address("chris@example.org"), mark, friends]


def test_add_address_accepts_a_group() -> None:
    header = MailboxListHeader("To", [])
    chris = Address("chris@example.org")
    group = Group("Friends", [Address("mark@example.org")])

    header.add_address(chris)
    header.add_address(group)

    assert header.get_address_list() == [chris, group]


def test_add_addresses_appends_and_set_addresses_replaces() -> None:
    chris = Address("chris@example.org")
    mark = Address("mark@example.org")
    header = MailboxListHeader("To", [chris])

    header.add_addresses([mark])
    assert header.get_address_list() == [chris, mark]

    header.set_addresses([mark])
    assert header.get_address_list() == [mark]
