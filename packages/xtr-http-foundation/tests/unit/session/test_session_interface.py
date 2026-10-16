"""The session this library ships answers the session contract."""

from __future__ import annotations

from xtr_http_foundation import MemorySessionStorage, Session, SessionInterface


def test_the_session_answers_the_contract() -> None:
    assert isinstance(Session(MemorySessionStorage()), SessionInterface)
