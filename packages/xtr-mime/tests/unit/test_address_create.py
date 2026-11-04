"""Addresses made from what a caller holds: an address as it is, or ``Name <address>`` parsed."""

from __future__ import annotations

from typing import cast

import pytest

from tests.support.address_reading import UNSAFE_IN_A_MESSAGE
from xtr_mime import Address
from xtr_mime.exception import InvalidArgumentError


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


def test_create_names_a_string_it_cannot_parse_escaped() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Address.create("<a@b\r\nBcc: v@e.x\udc80")

    message = str(caught.value)
    assert message == (
        'Could not parse "<a@b\\r\\nBcc: v@e.x\\udc80" to an "xtr_mime.Address" instance.'
    )
    assert not any(character in message for character in UNSAFE_IN_A_MESSAGE)


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
