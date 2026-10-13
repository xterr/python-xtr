from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.body import json_encode, normalize_body

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


async def _parts() -> AsyncIterator[bytes]:
    yield b"foo=bar"


def test_a_mapping_is_sent_as_a_form_and_says_so() -> None:
    headers: dict[str, list[str]] = {}

    assert normalize_body({"foo": "bar"}, headers) == b"foo=bar"
    assert headers["content-type"] == ["Content-Type: application/x-www-form-urlencoded"]


def test_a_field_with_nothing_in_it_is_left_out() -> None:
    headers: dict[str, list[str]] = {}

    assert normalize_body({"foo": "bar", "baz": {}}, headers) == b"foo=bar"


def test_a_form_with_no_fields_is_no_body_and_names_no_content_type() -> None:
    headers: dict[str, list[str]] = {}

    assert normalize_body({}, headers) == b""
    assert headers == {}


def test_a_content_type_the_caller_chose_is_kept() -> None:
    for content_type in (
        "application/x-www-form-urlencoded; charset=utf-8",
        "multipart/form-data; boundary=ABCDEF",
    ):
        headers = {"content-type": [f"Content-Type: {content_type}"]}

        _ = normalize_body({"foo": "bar"}, headers)

        assert headers["content-type"] == [f"Content-Type: {content_type}"]


def test_bytes_and_text_go_as_they_are() -> None:
    assert normalize_body(b"foo=bar") == b"foo=bar"
    assert normalize_body("héllo") == "héllo".encode()


def test_a_body_produced_in_pieces_is_passed_on_untouched() -> None:
    chunks = [b"foo", b"=bar"]
    produced = _parts()

    assert normalize_body(chunks) is chunks
    assert normalize_body(produced) is produced


def test_a_body_of_a_shape_nothing_can_be_made_of_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = normalize_body(object())

    assert str(raised.value) == (
        'Option "body" must be bytes, a string, a mapping or an iterable of bytes, "object" given.'
    )


def test_a_value_is_encoded_the_way_a_browser_can_read_it_back() -> None:
    assert json_encode({"foo": "bar"}) == b'{"foo":"bar"}'
    assert json_encode([1, 2]) == b"[1,2]"
    assert json_encode(1.0) == b"1.0"
    assert json_encode("héllo") == b'"h\\u00e9llo"'


def test_the_characters_that_break_out_of_a_document_are_escaped() -> None:
    assert json_encode("<a>&'\"") == b'"\\u003Ca\\u003E\\u0026\\u0027\\u0022"'


def test_a_backslash_at_the_end_of_a_string_is_left_alone() -> None:
    assert json_encode("a\\") == b'"a\\\\"'
    assert json_encode('a\\"b') == b'"a\\\\\\u0022b"'


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1, 2}])
def test_a_value_json_cannot_carry_is_refused(value: object) -> None:
    with pytest.raises(InvalidArgumentError, match='Invalid value for "json" option: '):
        _ = json_encode(value)
