"""The ended sessions a back-channel logout is remembered in."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import pytest
from xtr_cache import ArrayAdapter
from xtr_clock import MockClock

from xtr_security_http.oidc.oidc_ended_sessions import OidcEndedSessions

pytestmark = pytest.mark.anyio

_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)


def _pool() -> ArrayAdapter:
    """A pool shared by every server of the application, frozen at the test instant."""
    return ArrayAdapter(clock=MockClock(_FROZEN))


def _key(namespace: str, sid: str) -> str:
    """The key an ended session is remembered under."""
    return f"oidc_ended_session.{namespace}.{sha256(sid.encode()).hexdigest()}"


async def test_a_recorded_session_is_one_that_ended() -> None:
    sessions = OidcEndedSessions(_pool(), "main", 3600)

    await sessions.record("sid-1")

    assert await sessions.has("sid-1")


async def test_a_session_nothing_recorded_is_not_one_that_ended() -> None:
    sessions = OidcEndedSessions(_pool(), "main", 3600)

    assert not await sessions.has("sid-1")


async def test_the_entry_is_kept_under_the_namespaced_hash_of_the_sid() -> None:
    pool = _pool()
    sessions = OidcEndedSessions(pool, "main", 3600)

    await sessions.record("sid-1")

    assert set(pool.values()) == {_key("main", "sid-1")}


async def test_the_entry_lives_for_the_configured_lifetime() -> None:
    clock = MockClock(_FROZEN)
    sessions = OidcEndedSessions(ArrayAdapter(clock=clock), "main", 3600)

    await sessions.record("sid-1")
    clock.sleep(3599)
    assert await sessions.has("sid-1")

    clock.sleep(1)
    assert not await sessions.has("sid-1")


async def test_recording_the_same_end_twice_changes_nothing() -> None:
    sessions = OidcEndedSessions(_pool(), "main", 3600)

    await sessions.record("sid-1")
    await sessions.record("sid-1")

    assert await sessions.has("sid-1")


async def test_two_firewalls_never_read_each_others_entries() -> None:
    pool = _pool()
    main = OidcEndedSessions(pool, "main", 3600)
    api = OidcEndedSessions(pool, "api", 3600)

    await main.record("sid-1")

    assert not await api.has("sid-1")


async def test_the_pool_is_the_store_not_the_instance() -> None:
    """The logout token reaches any server; the session it names was opened by another."""
    pool = _pool()
    recording = OidcEndedSessions(pool, "main", 3600)
    asking = OidcEndedSessions(pool, "main", 3600)

    await recording.record("sid-1")

    assert await asking.has("sid-1")
