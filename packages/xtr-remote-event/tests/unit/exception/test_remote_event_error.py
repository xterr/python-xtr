from __future__ import annotations

from xtr_remote_event.exception import RemoteEventError


def test_it_is_an_exception() -> None:
    assert issubclass(RemoteEventError, Exception)
