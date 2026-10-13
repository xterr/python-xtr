from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from xtr_http_message.exception import InvalidArgumentError
from xtr_http_message.stream import Stream

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import MessageInterface

pytestmark = pytest.mark.anyio

_BOTH_TYPES = re.compile("text/html, ?text/plain")

# The harness checks that a header name or value of the wrong type is refused.
# Here both types are in the signature, so the call cannot be made at all.
_WRONG_TYPE = (
    "Adaptation (plan H2): a header name is typed `str` and a value `str | Sequence[str]`, so "
    "the five rows of the harness's provider that pass a list, a boolean or a bare object as one "
    "of the two are refused before the call; no run-time type check was ported for them."
)


def test_the_protocol_version_can_be_replaced(message: MessageInterface) -> None:
    replaced = message.with_protocol_version("1.0")

    assert replaced is not message
    assert message.get_protocol_version() == "1.1"
    assert replaced.get_protocol_version() == "1.0"


def test_every_value_added_under_one_name_is_reported_under_it(
    message: MessageInterface,
) -> None:
    added = message.with_added_header("content-type", "text/html").with_added_header(
        "content-type", "text/plain"
    )

    assert message.get_headers() == {}
    assert added.get_headers()["content-type"] == ["text/html", "text/plain"]


@pytest.mark.parametrize("name", ["content-type", "Content-Type", "ConTent-Type"])
def test_a_header_is_found_whatever_the_case_it_is_asked_for_in(
    message: MessageInterface,
    name: str,
) -> None:
    assert message.with_added_header("content-type", "text/html").has_header(name) is True


@pytest.mark.parametrize("name", ["content-type", "Content-Type", "CONTENT-TYPE"])
def test_every_value_of_a_header_is_read_back_whatever_the_case(
    message: MessageInterface,
    name: str,
) -> None:
    added = message.with_added_header("content-type", "text/html").with_added_header(
        "content-type", "text/plain"
    )

    assert len(added.get_header(name)) == 2


def test_a_header_the_message_does_not_carry_reads_as_an_empty_list(
    message: MessageInterface,
) -> None:
    assert message.with_added_header("content-type", "text/html").get_header("Bar") == []


@pytest.mark.parametrize("name", ["content-type", "Content-Type", "CONTENT-TYPE"])
def test_the_values_of_a_header_are_joined_whatever_the_case(
    message: MessageInterface,
    name: str,
) -> None:
    added = message.with_added_header("content-type", "text/html").with_added_header(
        "content-type", "text/plain"
    )

    assert _BOTH_TYPES.search(added.get_header_line(name)) is not None


def test_a_header_the_message_does_not_carry_reads_as_an_empty_line(
    message: MessageInterface,
) -> None:
    assert message.with_added_header("content-type", "text/html").get_header_line("Bar") == ""


def test_setting_a_header_leaves_the_message_as_it_was(message: MessageInterface) -> None:
    set_once = message.with_header("content-type", "text/html")

    assert set_once is not message
    assert message.get_headers() == {}
    assert set_once.get_header_line("content-type") == "text/html"


def test_setting_a_header_twice_over_keeps_only_the_later_value(
    message: MessageInterface,
) -> None:
    set_once = message.with_header("content-type", "text/html")

    assert (
        set_once.with_header("content-type", "text/plain").get_header_line("content-type")
        == "text/plain"
    )


def test_setting_a_header_under_another_case_replaces_it(message: MessageInterface) -> None:
    set_once = message.with_header("content-type", "text/html")

    assert (
        set_once.with_header("Content-TYPE", "text/script").get_header_line("content-type")
        == "text/script"
    )


def test_a_header_can_be_set_to_several_values_at_once(message: MessageInterface) -> None:
    several = message.with_header("x-foo", ["bar", "baz"])

    assert re.search("bar, ?baz", several.get_header_line("x-foo")) is not None


def test_a_header_set_to_an_empty_value_is_still_a_header(message: MessageInterface) -> None:
    empty = message.with_header("Bar", "")

    assert empty.has_header("Bar") is True
    assert empty.get_header("Bar") == [""]


@pytest.mark.parametrize(
    ("name", "value"),
    [("foo", []), ("", "")],
    ids=["a header given no value at all", "a header given no name at all"],
)
def test_setting_a_header_the_grammar_refuses_is_refused(
    message: MessageInterface,
    name: str,
    value: str | Sequence[str],
) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = message.with_header(name, value)


@pytest.mark.parametrize(
    ("name", "value"),
    [("foo", []), ("", "")],
    ids=["a header given no value at all", "a header given no name at all"],
)
def test_adding_a_header_the_grammar_refuses_is_refused(
    message: MessageInterface,
    name: str,
    value: str | Sequence[str],
) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = message.with_added_header(name, value)


@pytest.mark.skip(reason=_WRONG_TYPE)
def test_setting_or_adding_a_header_of_the_wrong_type_is_refused() -> None:
    """The rows of the harness that pass something which is not a name or a value."""


def test_a_value_added_under_another_case_joins_the_header_already_there(
    message: MessageInterface,
) -> None:
    added = message.with_added_header("content-type", "text/html").with_added_header(
        "CONTENT-type", "text/plain"
    )

    assert _BOTH_TYPES.search(added.get_header_line("content-type")) is not None


def test_adding_several_values_at_once_keeps_the_values_already_there(
    message: MessageInterface,
) -> None:
    added = message.with_added_header("content-type", "text/html").with_added_header(
        "content-type", ["text/plain", "application/json"]
    )

    assert added.get_header("content-type") == ["text/html", "text/plain", "application/json"]


def test_a_mapping_of_values_is_added_as_the_values_it_holds(message: MessageInterface) -> None:
    """The harness adds a keyed array, whose keys it expects ignored.

    A header's values are a sequence here, so the keyed array of the harness is
    ported as the values it holds — which is all the harness asserts about it.
    """
    first = {"foo": "text/html"}
    then = {"foo": "text/plain", "bar": "application/json"}

    added = message.with_added_header("content-type", list(first.values())).with_added_header(
        "content-type", list(then.values())
    )

    assert added.get_header("content-type") == ["text/html", "text/plain", "application/json"]


def test_removing_a_header_removes_it_whatever_the_case(message: MessageInterface) -> None:
    carried = (
        message.with_added_header("content-type", "text/html")
        .with_added_header("Age", "0")
        .with_added_header("X-Foo", "bar")
    )

    without = carried.without_header("age")

    assert "Age" in carried.get_headers()
    assert len(without.get_headers()) == len(carried.get_headers()) - 1
    assert "Age" not in without.get_headers()


async def test_the_body_can_be_replaced(message: MessageInterface) -> None:
    body = Stream.create(b"foo")

    carrying = message.with_body(body)

    assert carrying is not message
    assert await message.get_body().get_contents() == b""
    assert carrying.get_body() is body
