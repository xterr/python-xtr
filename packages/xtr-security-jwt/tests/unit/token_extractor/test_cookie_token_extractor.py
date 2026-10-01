"""The cookie extractor reads a token from a named cookie, or reports none."""

from __future__ import annotations

from tests.support.requests import make_request
from xtr_security_jwt.token_extractor.cookie_token_extractor import CookieTokenExtractor
from xtr_security_jwt.token_extractor.token_extractor_interface import TokenExtractorInterface


def test_it_implements_the_interface() -> None:
    assert TokenExtractorInterface in CookieTokenExtractor.__mro__


def test_it_reads_a_cookie() -> None:
    request = make_request(cookies={"BEARER": "cookie-token"})

    assert CookieTokenExtractor().extract(request) == "cookie-token"


def test_it_returns_none_without_the_cookie() -> None:
    assert CookieTokenExtractor().extract(make_request()) is None
