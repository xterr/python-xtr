"""The token a caller holds: an id, and the value that answers for it."""

from __future__ import annotations

from xtr_security_csrf import CsrfToken


def test_it_keeps_the_id_it_was_given() -> None:
    assert CsrfToken("foo", "value").get_id() == "foo"


def test_it_keeps_the_value_it_was_given() -> None:
    assert CsrfToken("foo", "value").get_value() == "value"


def test_it_holds_the_empty_value_when_none_was_minted() -> None:
    assert CsrfToken("foo").get_value() == ""


def test_it_reads_as_its_value() -> None:
    assert str(CsrfToken("foo", "value")) == "value"
