"""The query extractor reads a token from a named parameter, or reports none."""

from __future__ import annotations

from tests.support.requests import make_request
from xtr_security_jwt.token_extractor.query_parameter_token_extractor import (
    QueryParameterTokenExtractor,
)
from xtr_security_jwt.token_extractor.token_extractor_interface import TokenExtractorInterface


def test_it_implements_the_interface() -> None:
    assert TokenExtractorInterface in QueryParameterTokenExtractor.__mro__


def test_it_reads_a_parameter() -> None:
    request = make_request(query={"bearer": "query-token"})

    assert QueryParameterTokenExtractor().extract(request) == "query-token"


def test_it_returns_none_without_the_parameter() -> None:
    assert QueryParameterTokenExtractor().extract(make_request()) is None
