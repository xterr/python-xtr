"""What the message mixin promises beyond any one message class.

The readers and ``with_*`` methods themselves are exercised through the
classes that carry them; what is here is the mixin's own promise — that
nothing a caller is handed can be used to change the message it came from, and
that a copy made for a change shares nothing with the message it was copied
from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from xtr_http_message.exception import InvalidArgumentError
from xtr_http_message.response import Response

if TYPE_CHECKING:
    from collections.abc import Sequence

pytestmark = pytest.mark.anyio

# A character `str.lower` folds onto an ASCII letter: the Kelvin sign onto
# `k`. A header name is ASCII by its own grammar, so it may not match one.
_KELVIN = "\u212a"


def test_changing_the_mapping_of_headers_cannot_change_the_message() -> None:
    response = Response(200, {"Foo": "Bar"})

    headers = response.get_headers()
    assert isinstance(headers, dict)
    headers["Baz"] = ["Bam"]

    assert response.get_headers() == {"Foo": ["Bar"]}


def test_changing_the_values_of_a_header_cannot_change_the_message() -> None:
    response = Response(200, {"Foo": "Bar"})

    values = response.get_header("Foo")
    assert isinstance(values, list)
    values.append("Bam")

    assert response.get_header("Foo") == ["Bar"]


def test_changing_the_values_inside_the_mapping_cannot_change_the_message() -> None:
    response = Response(200, {"Foo": "Bar"})

    values = response.get_headers()["Foo"]
    assert isinstance(values, list)
    values.append("Bam")

    assert response.get_header("Foo") == ["Bar"]


def test_adding_to_a_header_cannot_reach_back_into_the_message_it_came_from() -> None:
    response = Response(200, {"Foo": "Bar"})

    _ = response.with_added_header("Foo", "Baz")

    assert response.get_header("Foo") == ["Bar"]


def test_two_changes_from_the_same_message_do_not_see_each_other() -> None:
    response = Response(200, {"Foo": "Bar"})

    first = response.with_added_header("Foo", "Baz")
    second = response.with_added_header("Foo", "Bam")

    assert (first.get_header("Foo"), second.get_header("Foo")) == (
        ["Bar", "Baz"],
        ["Bar", "Bam"],
    )


def test_replacing_a_header_cannot_reach_back_into_the_message_it_came_from() -> None:
    response = Response(200, {"Foo": "Bar"})

    _ = response.with_header("foO", "Bam")

    assert response.get_headers() == {"Foo": ["Bar"]}


def test_removing_a_header_cannot_reach_back_into_the_message_it_came_from() -> None:
    response = Response(200, {"Foo": "Bar", "Baz": "Bam"})

    _ = response.without_header("Foo")

    assert response.has_header("Foo") is True


def test_the_body_of_a_message_built_with_none_is_opened_once() -> None:
    response = Response()

    assert response.get_body() is response.get_body()


def test_two_messages_built_with_no_body_do_not_share_one() -> None:
    assert Response().get_body() is not Response().get_body()


def test_a_message_copied_for_a_change_keeps_reading_the_same_body() -> None:
    response = Response(200, None, b"Hello")

    assert response.with_header("Foo", "Bar").get_body() is response.get_body()


async def test_a_body_written_to_after_the_message_was_copied_is_seen_by_both() -> None:
    response = Response(200, None, b"Hello")
    copied = response.with_header("Foo", "Bar")

    await response.get_body().seek(0, 2)
    _ = await response.get_body().write(b" there")

    assert await copied.get_body().get_contents() == b"Hello there"


async def test_a_message_copied_before_its_body_was_opened_opens_its_own() -> None:
    response = Response()
    copied = response.with_header("Foo", "Bar")

    _ = await response.get_body().write(b"Hello")

    assert await copied.get_body().get_contents() == b""


def test_a_name_matching_only_once_lowercased_outside_ascii_is_not_the_header() -> None:
    response = Response(200, {"Key": "v"})

    assert not response.has_header(f"{_KELVIN}EY")


def test_no_value_is_read_under_a_name_that_only_matches_outside_ascii() -> None:
    response = Response(200, {"Key": "v"})

    assert (response.get_header(f"{_KELVIN}EY"), response.get_header_line(f"{_KELVIN}EY")) == (
        [],
        "",
    )


def test_a_name_matching_only_outside_ascii_removes_no_header() -> None:
    response = Response(200, {"Key": "v"})

    assert response.without_header(f"{_KELVIN}EY") is response


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(17, id="a-number"),
        pytest.param(None, id="nothing"),
        pytest.param(1.5, id="a-fraction"),
        pytest.param(["a", 17], id="a-number-among-values"),
        pytest.param([None], id="nothing-among-values"),
        pytest.param({"a": "b"}, id="a-mapping"),
        pytest.param(b"bytes", id="bytes"),
        pytest.param(object(), id="a-bare-object"),
    ],
)
def test_a_value_that_is_no_header_value_is_refused_as_one(value: object) -> None:
    wrong = cast("str | Sequence[str]", value)

    with pytest.raises(InvalidArgumentError, match="Header values must be RFC 7230 compatible"):
        _ = Response(200, {"H": wrong})


def test_a_value_that_is_no_header_value_is_refused_by_with_header() -> None:
    wrong = cast("str | Sequence[str]", cast("object", 17))

    with pytest.raises(InvalidArgumentError, match="Header values must be RFC 7230 compatible"):
        _ = Response().with_header("H", wrong)


def test_a_value_that_is_no_header_value_is_refused_by_with_added_header() -> None:
    wrong = cast("str | Sequence[str]", cast("object", 17))

    with pytest.raises(InvalidArgumentError, match="Header values must be RFC 7230 compatible"):
        _ = Response().with_added_header("H", wrong)
