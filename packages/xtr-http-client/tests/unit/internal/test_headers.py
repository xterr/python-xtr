from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.headers import normalize_headers, should_buffer

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def _written(headers: object) -> Mapping[str, str | Sequence[str]] | Sequence[str]:
    """Whatever an untyped caller wrote, which is what the refusals are for."""
    return cast("Mapping[str, str | Sequence[str]] | Sequence[str]", headers)


def test_a_name_and_its_value_become_one_line_keyed_by_the_lowered_name() -> None:
    assert normalize_headers({"Content-Type": "text/plain"}) == {
        "content-type": ["Content-Type: text/plain"],
    }


def test_several_values_for_one_name_become_several_lines() -> None:
    assert normalize_headers({"Set-Cookie": ["a=1", "b=2"]}) == {
        "set-cookie": ["Set-Cookie: a=1", "Set-Cookie: b=2"],
    }


def test_lines_are_taken_as_they_are_written_with_the_value_left_trimmed() -> None:
    assert normalize_headers(["Content-Type:  text/plain", "X-Trace: abc"]) == {
        "content-type": ["Content-Type: text/plain"],
        "x-trace": ["X-Trace: abc"],
    }


def test_a_value_that_is_not_text_is_written_out_as_text() -> None:
    assert normalize_headers(_written({"Content-Length": 5})) == {
        "content-length": ["Content-Length: 5"],
    }


def test_a_name_with_no_value_is_known_and_empty_so_no_default_fills_it_in() -> None:
    assert normalize_headers(_written({"Accept": None})) == {"accept": []}


def test_a_value_that_cannot_be_written_out_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = normalize_headers(_written({"X-Trace": object()}))

    assert (
        str(raised.value) == 'Invalid value for header "X-Trace": expected string, "object" given.'
    )


def test_a_line_that_is_not_text_is_refused_by_its_position() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = normalize_headers(_written([5]))

    assert str(raised.value) == 'Invalid value for header "0": expected string, "int" given.'


@pytest.mark.parametrize("value", ["a\rb", "a\nb", "a\0b"])
def test_a_value_that_would_split_the_head_is_refused(value: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = normalize_headers({"X-Trace": value})

    assert str(raised.value) == f'Invalid header: CR/LF/NUL found in "X-Trace: {value}".'


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("text/plain", True),
        ("text/html; charset=UTF-8", True),
        ("application/json", True),
        ("application/ld+json", True),
        ("application/xml", True),
        ("application/vnd.api+xml", True),
        ("application/octet-stream", False),
        ("image/png", False),
        ("", False),
    ],
)
def test_only_a_body_worth_rereading_is_buffered_by_default(
    content_type: str,
    expected: bool,
) -> None:
    assert should_buffer({"content-type": [content_type]}) is expected


def test_a_response_that_names_no_content_type_is_not_buffered() -> None:
    assert should_buffer({}) is False
