"""The target-path helper keeps a firewall's return trip on the session."""

from __future__ import annotations

import pytest
from xtr_http_foundation import MemorySessionStorage, Session

from xtr_security_http.util.target_path import (
    get_target_path,
    remove_target_path,
    save_target_path,
)

pytestmark = pytest.mark.anyio


def _session() -> Session:
    """Return a session over an empty in-memory storage."""
    return Session(MemorySessionStorage())


async def test_a_saved_path_is_kept_under_the_firewalls_key() -> None:
    session = _session()

    await save_target_path(session, "api", "https://example.com/protected?page=2")

    assert await get_target_path(session, "api") == "https://example.com/protected?page=2"


async def test_two_firewalls_keep_their_paths_apart() -> None:
    session = _session()

    await save_target_path(session, "api", "https://example.com/books")
    await save_target_path(session, "admin", "https://example.com/admin")

    assert await get_target_path(session, "api") == "https://example.com/books"
    assert await get_target_path(session, "admin") == "https://example.com/admin"


async def test_an_unsaved_path_is_none() -> None:
    assert await get_target_path(_session(), "api") is None


async def test_a_removed_path_is_gone() -> None:
    session = _session()
    await save_target_path(session, "api", "https://example.com/protected")

    await remove_target_path(session, "api")

    assert await get_target_path(session, "api") is None


async def test_a_removed_path_leaves_the_other_firewalls_alone() -> None:
    session = _session()
    await save_target_path(session, "api", "https://example.com/books")
    await save_target_path(session, "admin", "https://example.com/admin")

    await remove_target_path(session, "api")

    assert await get_target_path(session, "api") is None
    assert await get_target_path(session, "admin") == "https://example.com/admin"
