"""The created-token value object reports its token and signed flag."""

from __future__ import annotations

from xtr_security_jwt.signature.created_jws import CreatedJws


def test_it_reports_the_token_and_that_it_is_signed() -> None:
    created = CreatedJws("a.b.c", is_signed=True)

    assert created.get_token() == "a.b.c"
    assert created.is_signed() is True


def test_an_unsigned_token_reports_it() -> None:
    assert CreatedJws("a.b.", is_signed=False).is_signed() is False
