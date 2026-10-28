from __future__ import annotations

from xtr_notifier.exception import NotifierError, NotifierRuntimeError


def test_it_derives_from_the_package_base_and_is_a_runtime_error() -> None:
    assert issubclass(NotifierRuntimeError, NotifierError)
    assert issubclass(NotifierRuntimeError, RuntimeError)
