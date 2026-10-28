"""The listener that writes the session a stateful request reattached back out."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from starlette.datastructures import MutableHeaders
from xtr_http_foundation import MemorySessionStorage, Session, SessionStorageInterface
from xtr_http_foundation.exception import SessionError
from xtr_http_kernel.event import FinishRequestEvent, ResponseEvent

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.event_listener.save_session_listener import (
    PRIORITY,
    SaveSessionListener,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio


@final
class _CountingStorage:
    """A session storage counting the writes and deletes it is asked for."""

    __slots__ = ("deletes", "inner", "writes")

    def __init__(self) -> None:
        self.inner = MemorySessionStorage()
        self.writes: list[str] = []
        self.deletes: list[str] = []

    async def read(self, session_id: str) -> Mapping[str, object] | None:
        """Return what the inner storage holds under ``session_id``."""
        return await self.inner.read(session_id)

    async def write(
        self,
        session_id: str,
        data: Mapping[str, object],
        ttl: float | None,
    ) -> None:
        """Record the write, then hand it to the inner storage."""
        self.writes.append(session_id)
        await self.inner.write(session_id, data, ttl)

    async def delete(self, session_id: str) -> None:
        """Record the delete, then hand it to the inner storage."""
        self.deletes.append(session_id)
        await self.inner.delete(session_id)


@final
class _FailingStorage:
    """A session storage whose every write fails, loudly."""

    __slots__ = ()

    async def read(self, session_id: str) -> Mapping[str, object] | None:
        """Answer nothing: the entry never made it to the storage."""
        del session_id
        return None

    async def write(
        self,
        session_id: str,
        data: Mapping[str, object],
        ttl: float | None,
    ) -> None:
        """Refuse the write: a session that cannot be kept is not quietly lost."""
        del data, ttl
        raise SessionError(f"The storage refused to keep the session {session_id!r}.")

    async def delete(self, session_id: str) -> None:
        """Refuse the delete the same way."""
        raise SessionError(f"The storage refused to drop the session {session_id!r}.")


def test_the_counting_storage_satisfies_the_storage_contract() -> None:
    assert isinstance(_CountingStorage(), SessionStorageInterface)
    assert isinstance(_FailingStorage(), SessionStorageInterface)


def _a_response_over(
    bag: dict[str, object],
) -> tuple[ResponseEvent, MutableHeaders]:
    """Return a response event over ``bag``, beside its mutable headers."""
    message: dict[str, object] = {"type": "http.response.start", "status": 200, "headers": []}
    headers = MutableHeaders(scope=message)
    return ResponseEvent(make_message(), bag, 200, headers), headers


def _a_finish_over(bag: dict[str, object]) -> FinishRequestEvent:
    """Return a finish event over ``bag``."""
    return FinishRequestEvent(make_message(), bag)


def _parking(
    storage: SessionStorageInterface,
    *,
    cookie_value: str | None = None,
) -> tuple[dict[str, object], Session]:
    """Return a state bag carrying a parked session, and the session."""
    bag: dict[str, object] = {}
    session = Session(storage, cookie_value=cookie_value)
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return bag, session


async def test_a_request_without_a_session_is_left_alone() -> None:
    bag: dict[str, object] = {}
    event, headers = _a_response_over(bag)

    await SaveSessionListener().on_kernel_response(event)

    assert headers.get("set-cookie") is None


async def test_an_untouched_session_saves_nothing_and_mints_no_cookie() -> None:
    """A session nothing read or wrote must not tell the client to carry one."""
    storage = _CountingStorage()
    bag, _session = _parking(storage)
    event, headers = _a_response_over(bag)

    await SaveSessionListener().on_kernel_response(event)

    assert storage.writes == []
    assert headers.get("set-cookie") is None


async def test_a_used_fresh_session_is_saved_and_its_cookie_staged() -> None:
    storage = _CountingStorage()
    bag, session = _parking(storage)
    await session.set("a-key", "a-value")
    event, headers = _a_response_over(bag)

    await SaveSessionListener().on_kernel_response(event)

    assert storage.writes == [session.get_id()]
    assert await storage.inner.read(session.get_id()) == {"a-key": "a-value"}
    assert headers["set-cookie"].startswith(f"xtr_session={session.get_id()}")


async def test_a_reattached_session_saves_without_staging_a_cookie() -> None:
    storage = _CountingStorage()
    bag, session = _parking(storage, cookie_value="a" * 48)
    await session.set("a-key", "a-value")
    event, headers = _a_response_over(bag)

    await SaveSessionListener().on_kernel_response(event)

    assert storage.writes == [session.get_id()]
    assert headers.get("set-cookie") is None


async def test_the_finish_half_saves_what_an_unanswered_request_wrote() -> None:
    storage = _CountingStorage()
    bag, session = _parking(storage)
    await session.set("a-key", "a-value")

    await SaveSessionListener().on_kernel_finish_request(_a_finish_over(bag))

    assert storage.writes == [session.get_id()]


async def test_the_finish_half_leaves_a_request_without_a_session_alone() -> None:
    bag: dict[str, object] = {}

    await SaveSessionListener().on_kernel_finish_request(_a_finish_over(bag))

    assert not security_state_of(bag).attributes.get(SecurityRequestAttributes.SESSION_SAVED)


async def test_the_finish_half_skips_what_the_response_half_already_saved() -> None:
    storage = _CountingStorage()
    bag, session = _parking(storage)
    await session.set("a-key", "a-value")
    event, _headers = _a_response_over(bag)
    listener = SaveSessionListener()

    await listener.on_kernel_response(event)
    await listener.on_kernel_finish_request(_a_finish_over(bag))

    assert storage.writes == [session.get_id()]


async def test_a_failed_save_leaves_the_request_unmarked_so_a_later_half_retries() -> None:
    bag, session = _parking(_FailingStorage())
    await session.set("a-key", "a-value")
    event, _headers = _a_response_over(bag)
    listener = SaveSessionListener()

    with pytest.raises(SessionError):
        await listener.on_kernel_response(event)
    assert not security_state_of(bag).attributes.get(SecurityRequestAttributes.SESSION_SAVED)

    with pytest.raises(SessionError):
        await listener.on_kernel_finish_request(_a_finish_over(bag))


def test_the_subscriptions_save_on_the_response_and_on_every_finish() -> None:
    subscribed = SaveSessionListener.get_subscribed_events()

    assert subscribed[ResponseEvent] == ("on_kernel_response", PRIORITY)
    assert subscribed[FinishRequestEvent] == "on_kernel_finish_request"
    assert PRIORITY == -1000
