"""The reasons bag collects what a traceable wrapper reads back."""

from __future__ import annotations

from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons


def test_it_starts_empty() -> None:
    reasons = UnsupportedReasons()

    assert reasons.all() == ()


def test_it_collects_reasons_in_the_order_they_were_added() -> None:
    reasons = UnsupportedReasons()
    reasons.add("the request carries no bearer token")
    reasons.add("the request is not a POST")

    assert reasons.all() == ("the request carries no bearer token", "the request is not a POST")
