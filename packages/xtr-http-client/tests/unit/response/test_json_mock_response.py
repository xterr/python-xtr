from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from xtr_http_client import JsonMockResponse
from xtr_http_client.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

pytestmark = pytest.mark.anyio

URL = "https://example.com/orders"


async def test_a_document_nobody_wrote_is_the_document_null() -> None:
    async with JsonMockResponse().issue("GET", URL, {}) as response:
        assert await response.get_content() == b"null"
        assert response.get_header("content-type") == ["application/json"]


async def test_a_mapping_goes_out_as_a_json_object() -> None:
    written = JsonMockResponse({"foo": "bar", "ccc": 123})

    async with written.issue("GET", URL, {}) as response:
        assert await response.to_array() == {"foo": "bar", "ccc": 123}
        assert response.get_header("content-type") == ["application/json"]


async def test_a_string_goes_out_as_a_json_string() -> None:
    async with JsonMockResponse("foobarccc").issue("GET", URL, {}) as response:
        assert await response.get_content() == b'"foobarccc"'
        assert response.get_header("content-type") == ["application/json"]


async def test_a_number_keeps_the_kind_of_number_it_is() -> None:
    written = JsonMockResponse({"foo": 1.23, "ccc": 1.0, "baz": 10.0})

    async with written.issue("GET", URL, {}) as response:
        assert await response.to_array() == {"foo": 1.23, "ccc": 1.0, "baz": 10.0}


async def test_a_value_json_cannot_be_made_of_is_refused_where_it_is_written() -> None:
    with pytest.raises(InvalidArgumentError, match="JSON encoding failed: "):
        _ = JsonMockResponse(object())


@pytest.mark.parametrize(
    ("content_type", "headers"),
    [
        ("application/json", {}),
        ("application/json", {"x-foo": "ccc"}),
        ("application/problem+json", {"content-type": "application/problem+json"}),
        (
            "application/problem+json",
            {"x-foo": "ccc", "content-type": "application/problem+json"},
        ),
    ],
    ids=["nothing", "another header", "a content type", "a content type and another header"],
)
async def test_a_content_type_the_script_names_is_the_one_sent(
    content_type: str,
    headers: Mapping[str, str],
) -> None:
    written = JsonMockResponse(
        {"foo": "bar"},
        {"response_headers": headers, "http_code": 201},
    )

    async with written.issue("GET", URL, {}) as response:
        assert response.get_header("content-type") == [content_type]
        assert response.get_status_code() == 201


async def test_a_document_can_be_read_out_of_a_file(tmp_path: Path) -> None:
    path = tmp_path / "response.json"
    _ = path.write_text('{"foo": "bar"}', encoding="utf-8")

    async with JsonMockResponse.from_file(path).issue("GET", URL, {}) as response:
        assert await response.to_array() == {"foo": "bar"}
        assert response.get_header("content-type") == ["application/json"]


async def test_a_file_that_is_not_json_is_refused_where_it_is_named(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    _ = path.write_text("{not json", encoding="utf-8")

    with pytest.raises(
        InvalidArgumentError,
        match=re.escape(f'File "{path}" does not contain valid JSON.'),
    ):
        _ = JsonMockResponse.from_file(path)


async def test_a_file_that_is_not_there_is_refused_where_it_is_named(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    with pytest.raises(InvalidArgumentError, match=re.escape(f'File not found: "{path}".')):
        _ = JsonMockResponse.from_file(path)
