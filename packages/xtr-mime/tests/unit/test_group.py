"""A group is a display name over a list of addresses, possibly empty."""

from __future__ import annotations

import pytest

from xtr_mime import Address, Group
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError


def test_a_group_creates_its_members_from_addresses_and_strings() -> None:
    group = Group("Friends", [Address("fabien@example.com"), "helene@example.com"])

    assert group.get_name() == "Friends"
    assert group.get_addresses() == [
        Address("fabien@example.com"),
        Address("helene@example.com"),
    ]


def test_a_group_may_have_no_member() -> None:
    group = Group("undisclosed-recipients")

    assert group.get_name() == "undisclosed-recipients"
    assert group.get_addresses() == []


def test_a_member_string_may_carry_a_display_name() -> None:
    group = Group("Friends", ["Fabien <fabien@example.com>"])

    assert group.get_addresses()[0].get_name() == "Fabien"


def test_an_invalid_member_is_refused() -> None:
    with pytest.raises(RfcComplianceError):
        _ = Group("Friends", ["fab   pot@example.com"])


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="spaces"),
        pytest.param("\r\n\x00", id="control-characters-only"),
    ],
)
def test_a_group_without_a_display_name_is_refused(name: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Group(name)

    assert str(caught.value) == "A group must have a display name."


def test_control_characters_are_stripped_from_the_name() -> None:
    assert Group("a\x00b").get_name() == "ab"


def test_a_name_holding_a_lone_surrogate_is_refused() -> None:
    # A byte that failed to decode survives in a str as a lone surrogate, which is not text.
    with pytest.raises(RfcComplianceError, match="surrogate"):
        _ = Group("Friends \udcb1 \\ Family")


def test_the_members_cannot_be_changed_through_the_returned_list() -> None:
    group = Group("Friends", ["fabien@example.com"])

    group.get_addresses().clear()

    assert group.get_addresses() == [Address("fabien@example.com")]
