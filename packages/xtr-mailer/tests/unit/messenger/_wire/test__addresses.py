"""Addresses, groups and envelopes as a queued email carries them."""

from __future__ import annotations

import pytest
from xtr_mime import Address, Email, Group

from xtr_mailer import Envelope
from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.messenger._wire._addresses import (
    read_address,
    read_entry,
    read_envelope,
    write_address,
    write_entry,
    write_envelope,
)


def test_an_address_comes_back_with_its_name() -> None:
    address = Address("fabien@example.com", "Fabien Ü")

    assert read_address(write_address(address), "a") == address


def test_a_group_comes_back_with_its_members() -> None:
    group = Group("Team", [Address("a@example.com", "A"), "b@example.com"])

    back = read_entry(write_entry(group), "e")

    assert isinstance(back, Group)
    assert (back.get_name(), back.get_addresses()) == (group.get_name(), group.get_addresses())


def test_an_address_entry_comes_back_an_address() -> None:
    assert read_entry(write_entry(Address("a@example.com")), "e") == Address("a@example.com")


def test_a_group_of_more_members_than_an_address_list_holds_is_refused() -> None:
    members = [{"address": f"u{index}@example.com", "name": ""} for index in range(1001)]

    with pytest.raises(InvalidArgumentError, match=r"e\.addresses holds more than 1000 entries"):
        _ = read_entry({"group": "Team", "addresses": members}, "e")


def test_a_name_of_256_characters_is_read() -> None:
    assert (
        read_address({"address": "a@example.com", "name": "n" * 256}, "a").get_name() == "n" * 256
    )


@pytest.mark.parametrize(
    "data",
    [
        {"address": "a@example.com", "name": "n" * 257},
        {"group": "n" * 257, "addresses": []},
    ],
    ids=["address", "group"],
)
def test_a_name_longer_than_256_characters_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError, match="is longer than 256 characters"):
        _ = read_entry(data, "e")


@pytest.mark.parametrize(
    "data",
    [
        {"address": "not an address", "name": ""},
        {"address": "a" * 400 + "@example.com", "name": ""},
        {"address": "a@example.com", "name": "n" * 1000},
        {"address": "a@example.com\r\nBcc: victim@example.com", "name": ""},
    ],
    ids=["invalid", "long address", "long name", "line break"],
)
def test_an_address_its_class_or_its_limits_refuse_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = read_address(data, "a")

    assert "victim" not in str(raised.value)
    assert "a" * 65 not in str(raised.value)


def test_no_envelope_stays_none() -> None:
    assert write_envelope(None) is None
    assert read_envelope(None, "envelope") is None


def test_an_envelope_comes_back_with_its_sender_and_every_recipient() -> None:
    envelope = Envelope(
        Address("bounces@example.com", "Bounces"),
        [Address("to@example.com"), Address("hidden@example.com")],
    )

    back = read_envelope(write_envelope(envelope), "envelope")

    assert back is not None
    assert type(back) is Envelope
    assert back.get_sender() == envelope.get_sender()
    assert back.get_recipients() == envelope.get_recipients()


def test_an_envelope_read_from_the_headers_travels_as_the_addresses_it_gives() -> None:
    email = Email().from_("a@example.com").to(Address("to@example.com", "To")).bcc("b@example.com")

    back = read_envelope(write_envelope(Envelope.create(email)), "envelope")

    assert back is not None
    assert back.get_sender() == Address("a@example.com")
    assert back.get_recipients() == [Address("to@example.com"), Address("b@example.com")]


def test_an_envelope_without_a_recipient_is_refused() -> None:
    data: dict[str, object] = {
        "sender": {"address": "a@example.com", "name": ""},
        "recipients": [],
    }

    with pytest.raises(InvalidArgumentError, match="envelope is not an envelope"):
        _ = read_envelope(data, "envelope")
