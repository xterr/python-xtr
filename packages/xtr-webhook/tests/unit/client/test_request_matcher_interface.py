from __future__ import annotations

from xtr_webhook.client import MethodRequestMatcher, RequestMatcherInterface


def test_a_matcher_is_recognised_at_runtime() -> None:
    assert isinstance(MethodRequestMatcher("POST"), RequestMatcherInterface)


def test_something_that_cannot_match_is_not() -> None:
    assert not isinstance(object(), RequestMatcherInterface)
