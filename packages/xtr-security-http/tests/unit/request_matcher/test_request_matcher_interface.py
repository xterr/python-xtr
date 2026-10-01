"""The request matcher interface is a runtime-checkable protocol."""

from __future__ import annotations

from xtr_security_http.request_matcher.path_request_matcher import PathRequestMatcher
from xtr_security_http.request_matcher.request_matcher_interface import RequestMatcherInterface


def test_a_conforming_matcher_satisfies_the_interface() -> None:
    matcher = PathRequestMatcher(r"^/api")
    assert isinstance(matcher, RequestMatcherInterface)
    assert RequestMatcherInterface in type(matcher).__mro__


def test_a_bare_object_does_not_satisfy_the_interface() -> None:
    assert not isinstance(object(), RequestMatcherInterface)
