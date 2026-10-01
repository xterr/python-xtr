"""The chain extractor returns the first token any member finds."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from tests.support.requests import make_request
from xtr_security_http.access_token.access_token_extractor_interface import (
    AccessTokenExtractorInterface,
)
from xtr_security_http.access_token.chain_access_token_extractor import ChainAccessTokenExtractor
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.access_token.query_access_token_extractor import QueryAccessTokenExtractor

pytestmark = pytest.mark.anyio


def test_it_inherits_the_interface() -> None:
    assert AccessTokenExtractorInterface in ChainAccessTokenExtractor.__mro__


async def test_it_returns_the_first_token_found() -> None:
    chain = ChainAccessTokenExtractor(
        [HeaderAccessTokenExtractor(), QueryAccessTokenExtractor()],
    )

    from_query = await chain.extract_access_token(make_request(query="access_token=q"))
    from_header = await chain.extract_access_token(
        make_request(headers={"authorization": "Bearer h"}),
    )
    nothing = await chain.extract_access_token(make_request())

    assert from_query == "q"
    assert from_header == "h"
    assert nothing is None


def test_its_scheme_is_the_first_members_scheme() -> None:
    header = HeaderAccessTokenExtractor()
    chain = ChainAccessTokenExtractor([header, QueryAccessTokenExtractor()])

    assert chain.scheme() is header.scheme()


def test_an_empty_chain_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = ChainAccessTokenExtractor([])
