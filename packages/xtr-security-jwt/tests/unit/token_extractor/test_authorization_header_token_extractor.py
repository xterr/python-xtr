"""The header extractor reads a token after a scheme prefix, or reports none."""

from __future__ import annotations

from tests.support.requests import make_request
from xtr_security_jwt.token_extractor.authorization_header_token_extractor import (
    AuthorizationHeaderTokenExtractor,
)
from xtr_security_jwt.token_extractor.token_extractor_interface import TokenExtractorInterface


def test_it_implements_the_interface() -> None:
    assert TokenExtractorInterface in AuthorizationHeaderTokenExtractor.__mro__


def test_it_reads_a_bearer_token() -> None:
    request = make_request(headers={"Authorization": "Bearer the-token"})

    assert AuthorizationHeaderTokenExtractor().extract(request) == "the-token"


def test_it_returns_none_without_a_header() -> None:
    assert AuthorizationHeaderTokenExtractor().extract(make_request()) is None


def test_it_rejects_a_wrong_prefix() -> None:
    request = make_request(headers={"Authorization": "Basic the-token"})

    assert AuthorizationHeaderTokenExtractor().extract(request) is None


def test_it_matches_the_prefix_case_insensitively() -> None:
    request = make_request(headers={"Authorization": "bearer the-token"})

    assert AuthorizationHeaderTokenExtractor().extract(request) == "the-token"


def test_with_no_prefix_it_returns_the_whole_value() -> None:
    request = make_request(headers={"X-Token": "raw-token"})

    assert AuthorizationHeaderTokenExtractor("", "X-Token").extract(request) == "raw-token"
