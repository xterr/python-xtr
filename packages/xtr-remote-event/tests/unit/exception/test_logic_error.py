from __future__ import annotations

from xtr_remote_event.exception import LogicError, RemoteEventError


def test_it_derives_from_the_base() -> None:
    assert isinstance(LogicError("no consumer"), RemoteEventError)


def test_it_is_a_runtime_error() -> None:
    assert isinstance(LogicError("no consumer"), RuntimeError)
