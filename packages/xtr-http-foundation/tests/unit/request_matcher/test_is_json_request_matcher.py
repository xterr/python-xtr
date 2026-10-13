"""Whether the body of a request reads as JSON."""

from __future__ import annotations

import pytest
from xtr_http_message import ServerRequest, Stream

from xtr_http_foundation import IsJsonRequestMatcher


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("body", "is_valid"),
    [
        ("not json", False),
        ('"json_string"', True),
        ("11", True),
        ('["json", "array"]', True),
    ],
)
async def test_it_matches_a_body_that_reads_as_json(body: str, is_valid: bool) -> None:
    matcher = IsJsonRequestMatcher()
    request = ServerRequest("GET", "/", body=body.encode())

    assert await matcher.matches(request) is is_valid


@pytest.mark.anyio
async def test_it_refuses_a_body_of_no_bytes_at_all() -> None:
    matcher = IsJsonRequestMatcher()

    assert await matcher.matches(ServerRequest("GET", "/")) is False


@pytest.mark.anyio
async def test_it_refuses_a_body_that_is_not_text() -> None:
    matcher = IsJsonRequestMatcher()
    request = ServerRequest("GET", "/", body=b"\xff\xfe")

    assert await matcher.matches(request) is False


@pytest.mark.anyio
async def test_it_refuses_a_body_that_cannot_be_read() -> None:
    body = Stream.create(b'{"total": 4200}')
    await body.close()
    request = ServerRequest("GET", "/").with_body(body)

    assert await IsJsonRequestMatcher().matches(request) is False


@pytest.mark.anyio
async def test_it_reads_a_body_another_matcher_already_read() -> None:
    matcher = IsJsonRequestMatcher()
    request = ServerRequest("GET", "/", body=b'{"total": 4200}')

    assert await matcher.matches(request) is True
    assert await matcher.matches(request) is True
