"""Every storage this library ships answers the storage contract."""

from __future__ import annotations

from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface


def test_the_memory_storage_answers_the_contract() -> None:
    assert isinstance(MemorySessionStorage(), SessionStorageInterface)
