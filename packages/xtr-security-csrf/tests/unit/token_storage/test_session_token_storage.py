"""The storage that keeps its tokens in the session a request carries."""

from __future__ import annotations

import pytest
from xtr_http_foundation import MemorySessionStorage, Session

from xtr_security_csrf import (
    ClearableTokenStorageInterface,
    SessionTokenStorage,
    TokenNotFoundError,
    TokenStorageInterface,
)


@pytest.fixture
def session() -> Session:
    """Return a session nothing has touched yet, on the memory storage."""
    return Session(MemorySessionStorage())


@pytest.fixture
def storage(session: Session) -> SessionTokenStorage:
    """Return the token storage over that session, under the default namespace."""
    return SessionTokenStorage(session)


def test_it_answers_both_storage_contracts(storage: SessionTokenStorage) -> None:
    assert isinstance(storage, TokenStorageInterface)
    assert isinstance(storage, ClearableTokenStorageInterface)


@pytest.mark.anyio
async def test_it_stores_a_token_under_its_namespaced_id(
    storage: SessionTokenStorage,
    session: Session,
) -> None:
    await storage.set_token("foo", "value")

    assert await session.get("_csrf/foo") == "value"


@pytest.mark.anyio
async def test_it_reads_back_what_it_stored(storage: SessionTokenStorage) -> None:
    await storage.set_token("foo", "value")

    assert await storage.get_token("foo") == "value"


@pytest.mark.anyio
async def test_it_tells_whether_a_token_is_stored(storage: SessionTokenStorage) -> None:
    assert not await storage.has_token("foo")
    await storage.set_token("foo", "value")
    assert await storage.has_token("foo")


@pytest.mark.anyio
async def test_it_raises_when_asked_for_an_id_that_holds_nothing(
    storage: SessionTokenStorage,
) -> None:
    with pytest.raises(TokenNotFoundError) as raised:
        _ = await storage.get_token("foo")

    assert raised.value.get_token_id() == "foo"
    assert "does not exist" in str(raised.value)


@pytest.mark.anyio
async def test_it_removes_a_token_and_returns_what_it_held(storage: SessionTokenStorage) -> None:
    await storage.set_token("foo", "value")

    assert await storage.remove_token("foo") == "value"
    assert not await storage.has_token("foo")


@pytest.mark.anyio
async def test_it_removes_an_id_that_holds_nothing_without_complaint(
    storage: SessionTokenStorage,
) -> None:
    assert await storage.remove_token("foo") is None


@pytest.mark.anyio
async def test_a_token_survives_the_request_that_stored_it() -> None:
    backend = MemorySessionStorage()
    session = Session(backend)
    storage = SessionTokenStorage(session)
    await storage.set_token("foo", "value")
    await session.save()

    again = SessionTokenStorage(Session(backend, cookie_value=session.get_id()))

    assert await again.get_token("foo") == "value"


@pytest.mark.anyio
async def test_clear_drops_every_token_it_minted_and_nothing_else(
    storage: SessionTokenStorage,
    session: Session,
) -> None:
    await storage.set_token("foo", "value")
    await storage.set_token("bar", "other")
    await session.set("theme", "dark")

    await storage.clear()

    assert not await storage.has_token("foo")
    assert not await storage.has_token("bar")
    assert await session.get("theme") == "dark"


@pytest.mark.anyio
async def test_clear_leaves_a_session_that_holds_no_tokens_alone(
    storage: SessionTokenStorage,
    session: Session,
) -> None:
    await session.set("theme", "dark")

    await storage.clear()

    assert await session.get("theme") == "dark"


@pytest.mark.anyio
async def test_a_token_dropped_by_hand_leaves_no_list_behind(
    storage: SessionTokenStorage,
    session: Session,
) -> None:
    await storage.set_token("foo", "value")
    _ = await storage.remove_token("foo")

    assert not await session.has("_csrf")


@pytest.mark.anyio
async def test_a_custom_namespace_keeps_its_tokens_apart(session: Session) -> None:
    first = SessionTokenStorage(session, namespace="app1")
    second = SessionTokenStorage(session, namespace="app2")

    await first.set_token("foo", "value")

    assert await session.has("app1/foo")
    assert not await session.has("app2/foo")
    assert not await second.has_token("foo")
