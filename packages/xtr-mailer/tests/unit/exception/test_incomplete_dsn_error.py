from __future__ import annotations

from xtr_mailer.exception import IncompleteDsnError, InvalidArgumentError


def test_it_is_an_invalid_argument() -> None:
    assert issubclass(IncompleteDsnError, InvalidArgumentError)


def test_its_message_is_what_is_missing() -> None:
    assert str(IncompleteDsnError("User is not set.")) == "User is not set."
