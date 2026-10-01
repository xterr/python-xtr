"""The header extractor reads a bearer token from a request header."""

from __future__ import annotations

# Test tokens and scheme words are not secrets.
# ruff: noqa: S105, S106
import pytest
from fastapi.security import APIKeyHeader, HTTPBearer

from tests.support.requests import make_request
from xtr_security_http.access_token.access_token_extractor_interface import (
    AccessTokenExtractorInterface,
)
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor

pytestmark = pytest.mark.anyio


def test_it_inherits_the_interface() -> None:
    assert AccessTokenExtractorInterface in HeaderAccessTokenExtractor.__mro__


async def test_it_reads_a_bearer_token() -> None:
    extractor = HeaderAccessTokenExtractor()

    token = await extractor.extract_access_token(
        make_request(headers={"authorization": "Bearer t"})
    )

    assert token == "t"
    assert isinstance(extractor.scheme(), HTTPBearer)


async def test_it_returns_none_without_a_token() -> None:
    extractor = HeaderAccessTokenExtractor()

    assert await extractor.extract_access_token(make_request()) is None


async def test_it_supports_a_custom_header_and_type() -> None:
    extractor = HeaderAccessTokenExtractor(header_name="X-Api-Key", token_type="")

    token = await extractor.extract_access_token(make_request(headers={"x-api-key": "raw"}))

    assert token == "raw"
    assert isinstance(extractor.scheme(), APIKeyHeader)


async def test_it_strips_a_custom_token_type() -> None:
    extractor = HeaderAccessTokenExtractor(header_name="X-Token", token_type="Token")

    token = await extractor.extract_access_token(make_request(headers={"x-token": "Token abc"}))

    assert token == "abc"


async def test_it_rejects_a_wrong_token_type() -> None:
    extractor = HeaderAccessTokenExtractor(header_name="X-Token", token_type="Token")

    token = await extractor.extract_access_token(make_request(headers={"x-token": "Bearer abc"}))

    assert token is None
