"""The chain extractor returns the first token any member finds, in order."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from tests.support.requests import make_request
from xtr_security_jwt.token_extractor.authorization_header_token_extractor import (
    AuthorizationHeaderTokenExtractor,
)
from xtr_security_jwt.token_extractor.chain_token_extractor import ChainTokenExtractor
from xtr_security_jwt.token_extractor.query_parameter_token_extractor import (
    QueryParameterTokenExtractor,
)
from xtr_security_jwt.token_extractor.token_extractor_interface import TokenExtractorInterface


def test_it_implements_the_interface() -> None:
    assert TokenExtractorInterface in ChainTokenExtractor.__mro__


def test_it_returns_the_first_token_found() -> None:
    chain = ChainTokenExtractor(
        [QueryParameterTokenExtractor(), AuthorizationHeaderTokenExtractor()],
    )
    request = make_request(headers={"Authorization": "Bearer header-token"})

    assert chain.extract(request) == "header-token"


def test_it_returns_none_when_none_find_a_token() -> None:
    chain = ChainTokenExtractor([AuthorizationHeaderTokenExtractor()])

    assert chain.extract(make_request()) is None


def test_it_refuses_no_extractors() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = ChainTokenExtractor([])


def test_it_is_iterable() -> None:
    header = AuthorizationHeaderTokenExtractor()
    chain = ChainTokenExtractor([header])

    assert list(chain) == [header]
