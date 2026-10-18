"""The query extractor reads a token from a query-string parameter."""

from __future__ import annotations

# Test token values are not secrets.
# ruff: noqa: S105
import pytest

from tests.support.messages import make_message
from xtr_security_http.access_token.access_token_extractor_interface import (
    AccessTokenExtractorInterface,
)
from xtr_security_http.access_token.query_access_token_extractor import QueryAccessTokenExtractor

pytestmark = pytest.mark.anyio


def test_it_inherits_the_interface() -> None:
    assert AccessTokenExtractorInterface in QueryAccessTokenExtractor.__mro__


async def test_it_reads_the_parameter() -> None:
    extractor = QueryAccessTokenExtractor()

    token = await extractor.extract_access_token(make_message(query="access_token=q"))

    assert token == "q"


async def test_it_returns_none_without_the_parameter() -> None:
    assert await QueryAccessTokenExtractor().extract_access_token(make_message()) is None
