from __future__ import annotations

import json

import pytest

from tests.support.fake_response import FakeResponse
from tests.support.fake_stream import FakeStream
from xtr_http_client.exception._http_error_message import build_message

pytestmark = pytest.mark.anyio

_STATUS_LINE = "HTTP/1.1 400 Bad Request"
_NO_MESSAGE = f'{_STATUS_LINE} returned for "http://example.com".'
_WITH_MESSAGE = "An error occurred\n\nSome details"


def _response(
    content_type: str,
    body: bytes,
    *,
    url: str = "http://example.com",
) -> FakeResponse:
    return FakeResponse(
        status_code=400,
        url=url,
        response_headers=[_STATUS_LINE, f"Content-Type: {content_type}"],
        body=FakeStream(body),
    )


def _long_error_body() -> bytes:
    return json.dumps({"title": "An error occurred", "detail": "x" * (64 * 1024)}).encode()


@pytest.mark.parametrize(
    ("content_type", "body", "expected"),
    [
        (
            "application/ld+json",
            b'{"hydra:title": "An error occurred", "hydra:description": "Some details"}',
            _WITH_MESSAGE,
        ),
        (
            "application/problem+json",
            b'{"title": "An error occurred", "detail": "Some details"}',
            _WITH_MESSAGE,
        ),
        (
            "application/vnd.api+json",
            b'{"title": "An error occurred", "detail": "Some details"}',
            _WITH_MESSAGE,
        ),
        (
            "application/json",
            b'{"title": "An error occurred", "detail": {"field_name": ["Some details"]}}',
            _NO_MESSAGE,
        ),
    ],
)
async def test_a_json_error_document_names_what_went_wrong(
    content_type: str,
    body: bytes,
    expected: str,
) -> None:
    assert await build_message(_response(content_type, body)) == expected


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (b'{"hydra:title": "An error occurred"}', "An error occurred"),
        (b'{"hydra:description": "Some details"}', "Some details"),
        (b'{"title": "An error occurred"}', "An error occurred"),
        (b'{"detail": "Some details"}', "Some details"),
        (b'{"title": "An error occurred", "detail": null}', "An error occurred"),
        (b'{"title": 42, "detail": "Some details"}', "42\n\nSome details"),
        (b'{"title": true, "detail": "Some details"}', "1\n\nSome details"),
    ],
)
async def test_one_of_the_two_fields_is_enough(body: bytes, expected: str) -> None:
    assert await build_message(_response("application/problem+json", body)) == expected


@pytest.mark.parametrize(
    "body",
    [b"null", b"[]", b"0", b'""', b"not json", b"[1, 2]", b'{"message": "nope"}'],
)
async def test_a_body_that_carries_no_error_document_leaves_the_status_line(body: bytes) -> None:
    assert await build_message(_response("application/json", body)) == _NO_MESSAGE


async def test_only_the_head_of_a_long_body_is_parsed() -> None:
    response = _response("application/problem+json", _long_error_body(), url="http://example.com/")

    message = await build_message(response)

    assert message == 'HTTP/1.1 400 Bad Request returned for "http://example.com/".'


async def test_the_body_is_read_once_and_stays_whole() -> None:
    response = _response(
        "application/problem+json",
        b'{"title": "An error occurred", "detail": "Some details"}',
    )

    _ = await build_message(response)

    assert response.content_reads == 1
    assert await response.get_content(throw=False) == (
        b'{"title": "An error occurred", "detail": "Some details"}'
    )


async def test_a_body_the_head_does_not_call_json_is_never_read() -> None:
    response = _response("text/plain", _long_error_body())

    message = await build_message(response)

    assert message == _NO_MESSAGE
    assert response.content_reads == 0


async def test_without_a_status_line_the_code_and_the_url_are_the_message() -> None:
    response = FakeResponse(
        status_code=404,
        url="http://example.com/missing",
        response_headers=["Content-Type: text/plain"],
    )

    assert await build_message(response) == 'HTTP 404 returned for "http://example.com/missing".'


async def test_the_status_line_of_the_last_response_is_the_one_that_counts() -> None:
    response = FakeResponse(
        status_code=400,
        url="http://example.com",
        response_headers=[
            "HTTP/1.1 302 Found",
            "Location: http://example.com",
            "HTTP/2 400 Bad Request",
            "Content-Type: text/plain",
        ],
    )

    assert (
        await build_message(response) == 'HTTP/2 400 Bad Request returned for "http://example.com".'
    )


async def test_a_content_type_before_the_status_line_still_says_json() -> None:
    response = _response("application/json", b'{"title": "An error occurred"}')
    response.response_headers = [
        "HTTP/1.1 302 Found",
        "HTTP/1.1 400 Bad Request",
        "Content-Type: application/json",
    ]

    assert await build_message(response) == "An error occurred"


async def test_a_head_that_is_not_a_list_of_lines_leaves_the_code_and_the_url() -> None:
    response = FakeResponse(
        status_code=400,
        url="http://example.com",
        response_headers={"content-type": ("application/json",)},
        body=FakeStream(b'{"title": "An error occurred"}'),
    )

    assert await build_message(response) == 'HTTP 400 returned for "http://example.com".'
    assert response.content_reads == 0


async def test_a_content_type_written_before_the_status_line_it_belongs_to_is_read() -> None:
    response = FakeResponse(
        status_code=400,
        url="http://example.com",
        response_headers=[
            "HTTP/1.1 302 Found",
            "Content-Type: application/json",
            "HTTP/1.1 400 Bad Request",
        ],
        body=FakeStream(b'{"title": "An error occurred"}'),
    )

    assert await build_message(response) == "An error occurred"
