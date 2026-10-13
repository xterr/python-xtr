from __future__ import annotations

from xtr_http_foundation.exception import HttpFoundationError


def test_it_is_an_exception() -> None:
    assert issubclass(HttpFoundationError, Exception)


def test_it_carries_the_message_it_is_given() -> None:
    assert str(HttpFoundationError("the request said nothing about it")) == (
        "the request said nothing about it"
    )
