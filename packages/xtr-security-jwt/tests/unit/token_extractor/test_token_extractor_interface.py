"""The extractor interface is runtime-checkable against a conforming extractor."""

from __future__ import annotations

from xtr_security_jwt.token_extractor.cookie_token_extractor import CookieTokenExtractor
from xtr_security_jwt.token_extractor.token_extractor_interface import TokenExtractorInterface


def test_a_conforming_extractor_satisfies_the_interface() -> None:
    assert isinstance(CookieTokenExtractor(), TokenExtractorInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), TokenExtractorInterface)
