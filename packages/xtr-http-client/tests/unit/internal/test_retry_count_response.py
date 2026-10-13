from __future__ import annotations

from collections.abc import Mapping

import pytest

from tests.support.fake_response import FakeResponse
from tests.support.fake_stream import FakeStream
from xtr_http_client.internal.retry_count_response import with_retry_count

pytestmark = pytest.mark.anyio


def _answered(status_code: int = 200, body: bytes = b"") -> FakeResponse:
    return FakeResponse(status_code=status_code, body=FakeStream(body))


async def test_the_number_of_tries_is_one_entry_of_the_record() -> None:
    async with with_retry_count(_answered(), 2) as response:
        assert response.get_info("retry_count") == 2


async def test_the_whole_record_carries_it_beside_the_transfer_s_own() -> None:
    async with with_retry_count(_answered(503), 1) as response:
        whole = response.get_info()

        assert isinstance(whole, Mapping)
        assert whole["retry_count"] == 1
        assert whole["http_code"] == 503


async def test_every_other_entry_is_the_wrapped_response_s() -> None:
    async with with_retry_count(_answered(503), 1) as response:
        assert response.get_info("http_code") == 503
        assert response.get_info("nothing_recorded") is None


async def test_the_status_line_and_headers_are_the_wrapped_response_s() -> None:
    inner = _answered(503).with_header("X-Kind", "thing").with_status(504, "Gateway Timeout")

    async with with_retry_count(inner, 1) as response:
        assert response.get_status_code() == 504
        assert response.get_reason_phrase() == "Gateway Timeout"
        assert response.get_protocol_version() == "1.1"
        assert response.has_header("x-kind")
        assert response.get_header("x-kind") == ("thing",)
        assert response.get_header_line("x-kind") == "thing"
        assert dict(response.get_headers()) == {"X-Kind": ("thing",)}


async def test_a_copy_still_reports_the_number_of_tries() -> None:
    async with with_retry_count(_answered(), 3) as response:
        for copy in (
            response.with_status(500),
            response.with_protocol_version("2"),
            response.with_header("X-Kind", "thing"),
            response.with_added_header("X-Kind", "other"),
            response.without_header("X-Kind"),
            response.with_body(FakeStream(b"replaced")),
        ):
            assert copy.get_info("retry_count") == 3


async def test_the_body_is_the_wrapped_response_s_own() -> None:
    inner = _answered(body=b"payload")

    async with with_retry_count(inner, 1) as response:
        assert response.get_body() is inner.get_body()
        assert await response.get_content() == b"payload"


async def test_a_json_body_decodes_through_the_wrapper() -> None:
    async with with_retry_count(_answered(body=b'{"id": 7}'), 1) as response:
        assert await response.to_array() == {"id": 7}


async def test_leaving_the_block_closes_the_wrapped_body() -> None:
    body = FakeStream(b"payload")
    inner = FakeResponse(body=body)

    async with with_retry_count(inner, 1):
        assert not body.closed

    assert body.closed


async def test_cancelling_cancels_the_wrapped_transfer() -> None:
    inner = _answered()

    await with_retry_count(inner, 1).cancel()

    assert inner.canceled
