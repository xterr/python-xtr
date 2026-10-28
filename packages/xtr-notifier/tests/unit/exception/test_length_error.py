from __future__ import annotations

from xtr_notifier.exception import LengthError, LogicError, NotifierError


def test_it_derives_from_the_package_base_and_is_a_logic_error() -> None:
    assert issubclass(LengthError, NotifierError)
    assert issubclass(LengthError, LogicError)
