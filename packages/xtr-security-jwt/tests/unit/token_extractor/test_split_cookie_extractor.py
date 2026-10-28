"""The split-cookie extractor rejoins a token spread across named cookies."""

from __future__ import annotations

from tests.support.messages import make_message
from xtr_security_jwt.token_extractor.split_cookie_extractor import SplitCookieExtractor
from xtr_security_jwt.token_extractor.token_extractor_interface import TokenExtractorInterface


def test_it_implements_the_interface() -> None:
    assert TokenExtractorInterface in SplitCookieExtractor.__mro__


def test_it_rejoins_the_parts() -> None:
    request = make_message(cookies={"h": "a", "p": "b", "s": "c"})

    assert SplitCookieExtractor(("h", "p", "s")).extract(request) == "a.b.c"


def test_it_needs_every_cookie() -> None:
    request = make_message(cookies={"h": "a", "p": "b"})

    assert SplitCookieExtractor(("h", "p", "s")).extract(request) is None


def test_with_no_cookies_it_returns_none() -> None:
    assert SplitCookieExtractor(()).extract(make_message()) is None
