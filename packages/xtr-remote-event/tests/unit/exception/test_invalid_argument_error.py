from __future__ import annotations

from xtr_remote_event.exception import InvalidArgumentError, RemoteEventError


def test_it_derives_from_the_base() -> None:
    assert isinstance(InvalidArgumentError("bad"), RemoteEventError)


def test_it_is_a_value_error() -> None:
    assert isinstance(InvalidArgumentError("bad"), ValueError)
