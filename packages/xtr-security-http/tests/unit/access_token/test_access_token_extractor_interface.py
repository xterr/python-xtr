"""The access-token extractor interface is a runtime-checkable protocol."""

from __future__ import annotations

from xtr_security_http.access_token.access_token_extractor_interface import (
    AccessTokenExtractorInterface,
)
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor


def test_a_conforming_extractor_satisfies_the_interface() -> None:
    assert isinstance(HeaderAccessTokenExtractor(), AccessTokenExtractorInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AccessTokenExtractorInterface)
