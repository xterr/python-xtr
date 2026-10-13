"""Every matcher this library ships answers the matcher contract."""

from __future__ import annotations

import pytest

from xtr_http_foundation import (
    AttributesRequestMatcher,
    ChainRequestMatcher,
    HeaderRequestMatcher,
    HostRequestMatcher,
    IpsRequestMatcher,
    IsJsonRequestMatcher,
    MethodRequestMatcher,
    PathRequestMatcher,
    PortRequestMatcher,
    QueryParameterRequestMatcher,
    RequestMatcherInterface,
    SchemeRequestMatcher,
)


def _name(matcher: object) -> str:
    return type(matcher).__name__


@pytest.mark.parametrize(
    "matcher",
    [
        AttributesRequestMatcher({}),
        ChainRequestMatcher([]),
        HeaderRequestMatcher("x-foo"),
        HostRequestMatcher(".*"),
        IpsRequestMatcher("127.0.0.1"),
        IsJsonRequestMatcher(),
        MethodRequestMatcher("GET"),
        PathRequestMatcher("/"),
        PortRequestMatcher(80),
        QueryParameterRequestMatcher("foo"),
        SchemeRequestMatcher("https"),
    ],
    ids=_name,
)
def test_every_matcher_answers_the_contract(matcher: RequestMatcherInterface) -> None:
    assert isinstance(matcher, RequestMatcherInterface)
