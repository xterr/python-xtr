"""The header extractor reads a bearer token from a request header."""

from __future__ import annotations

# Test tokens and scheme words are not secrets.
# ruff: noqa: S105, S106
import pytest

from tests.support.messages import make_message
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
        make_message(headers={"authorization": "Bearer t"}),
    )

    assert token == "t"


async def test_it_returns_none_without_a_token() -> None:
    extractor = HeaderAccessTokenExtractor()

    assert await extractor.extract_access_token(make_message()) is None


async def test_it_returns_none_for_a_malformed_header() -> None:
    extractor = HeaderAccessTokenExtractor()

    bare = await extractor.extract_access_token(make_message(headers={"authorization": "Bearer"}))
    basic = await extractor.extract_access_token(
        make_message(headers={"authorization": "Basic dXNlcg=="}),
    )

    assert bare is None
    assert basic is None


async def test_the_scheme_word_is_matched_without_regard_to_case() -> None:
    extractor = HeaderAccessTokenExtractor()

    token = await extractor.extract_access_token(
        make_message(headers={"authorization": "bearer t"}),
    )

    assert token == "t"


async def test_it_supports_a_custom_header_and_type() -> None:
    extractor = HeaderAccessTokenExtractor(header_name="X-Api-Key", token_type="")

    token = await extractor.extract_access_token(make_message(headers={"x-api-key": "raw"}))

    assert token == "raw"


async def test_it_strips_a_custom_token_type() -> None:
    extractor = HeaderAccessTokenExtractor(header_name="X-Token", token_type="Token")

    token = await extractor.extract_access_token(make_message(headers={"x-token": "Token abc"}))

    assert token == "abc"


async def test_it_rejects_a_wrong_token_type() -> None:
    extractor = HeaderAccessTokenExtractor(header_name="X-Token", token_type="Token")

    token = await extractor.extract_access_token(make_message(headers={"x-token": "Bearer abc"}))

    assert token is None
