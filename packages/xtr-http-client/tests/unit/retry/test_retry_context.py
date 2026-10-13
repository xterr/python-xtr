from __future__ import annotations

from collections.abc import Mapping

import pytest

from tests.support.fake_response import FakeResponse
from xtr_http_client.internal.option_merge import as_options
from xtr_http_client.retry import RetryContext

pytestmark = pytest.mark.anyio


def _nothing_came_back() -> RetryContext:
    return RetryContext("GET", "https://example.com/", as_options({}), 0, None)


async def test_the_status_code_of_an_attempt_nothing_came_back_from_is_zero() -> None:
    assert _nothing_came_back().get_status_code() == 0


async def test_the_whole_info_of_an_attempt_nothing_came_back_from_is_empty() -> None:
    assert _nothing_came_back().get_info() == {}


async def test_one_info_entry_of_an_attempt_nothing_came_back_from_is_none() -> None:
    assert _nothing_came_back().get_info("http_code") is None


async def test_the_status_code_is_the_one_the_answer_came_back_with() -> None:
    async with FakeResponse(status_code=503) as response:
        context = RetryContext("GET", "https://example.com/", as_options({}), 2, response)

        assert context.get_status_code() == 503
        assert context.retry_count == 2


async def test_the_info_is_the_answer_s_own() -> None:
    async with FakeResponse(status_code=503, method="PUT") as response:
        context = RetryContext("PUT", "https://example.com/", as_options({}), 0, response)

        assert context.get_info("http_method") == "PUT"
        whole = context.get_info()
        assert isinstance(whole, Mapping)
        assert whole["http_code"] == 503
