"""The default manager: mint, mask, store, and check what comes back."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_foundation import MemorySessionStorage, Session

from xtr_security_csrf import (
    CsrfToken,
    CsrfTokenManager,
    CsrfTokenManagerInterface,
    SessionTokenStorage,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def session() -> Session:
    """Return a session nothing has touched yet, on the memory storage."""
    return Session(MemorySessionStorage())


def _manager(
    session: Session,
    namespace: str | Callable[[], str] | None = None,
) -> CsrfTokenManager:
    return CsrfTokenManager(SessionTokenStorage(session), namespace=namespace)


@pytest.mark.anyio
async def test_it_answers_the_manager_contract(session: Session) -> None:
    assert isinstance(_manager(session), CsrfTokenManagerInterface)


@pytest.mark.anyio
async def test_a_minted_token_checks_out(session: Session) -> None:
    manager = _manager(session)

    token = await manager.get_token("foo")

    assert await manager.is_token_valid(token)


@pytest.mark.anyio
async def test_asking_twice_answers_two_tokens_that_both_check_out(session: Session) -> None:
    manager = _manager(session)

    first = await manager.get_token("foo")
    second = await manager.get_token("foo")

    assert first.get_value() != second.get_value()
    assert await manager.is_token_valid(first)
    assert await manager.is_token_valid(second)


@pytest.mark.anyio
async def test_a_wrong_value_does_not_check_out(session: Session) -> None:
    manager = _manager(session)
    _ = await manager.get_token("foo")

    assert not await manager.is_token_valid(CsrfToken("foo", "not-the-value"))


@pytest.mark.anyio
async def test_a_value_minted_for_another_id_does_not_check_out(session: Session) -> None:
    manager = _manager(session)
    token = await manager.get_token("foo")

    assert not await manager.is_token_valid(CsrfToken("bar", token.get_value()))


@pytest.mark.anyio
async def test_a_token_nothing_is_stored_under_does_not_check_out(session: Session) -> None:
    manager = _manager(session)

    assert not await manager.is_token_valid(CsrfToken("never-minted", "whatever"))


@pytest.mark.anyio
async def test_a_malformed_presented_value_does_not_check_out_nor_raise(session: Session) -> None:
    manager = _manager(session)
    _ = await manager.get_token("foo")

    for value in ("no dots at all", "a.b.c", "..", "one.two.three.four"):
        assert not await manager.is_token_valid(CsrfToken("foo", value))


@pytest.mark.anyio
async def test_refreshing_replaces_the_stored_value(session: Session) -> None:
    manager = _manager(session)
    minted = await manager.get_token("foo")

    refreshed = await manager.refresh_token("foo")

    assert not await manager.is_token_valid(minted)
    assert await manager.is_token_valid(refreshed)


@pytest.mark.anyio
async def test_refreshing_an_id_that_held_nothing_mints_one(session: Session) -> None:
    manager = _manager(session)

    token = await manager.refresh_token("foo")

    assert await manager.is_token_valid(token)


@pytest.mark.anyio
async def test_removing_returns_the_stored_value_and_empties_the_id(session: Session) -> None:
    manager = _manager(session)
    minted = await manager.get_token("foo")

    removed = await manager.remove_token("foo")

    assert removed is not None
    assert removed != minted.get_value()
    assert not await manager.is_token_valid(minted)
    assert await manager.remove_token("foo") is None


@pytest.mark.anyio
async def test_a_removed_id_mints_a_fresh_token_next_time(session: Session) -> None:
    manager = _manager(session)
    minted = await manager.get_token("foo")
    _ = await manager.remove_token("foo")

    again = await manager.get_token("foo")

    assert again.get_value() != minted.get_value()
    assert await manager.is_token_valid(again)


@pytest.mark.anyio
async def test_ids_are_stored_under_their_namespace(session: Session) -> None:
    manager = _manager(session, namespace="https-")

    _ = await manager.get_token("foo")

    assert await session.has("_csrf/https-foo")


@pytest.mark.anyio
async def test_a_token_minted_under_one_namespace_does_not_answer_for_another(
    session: Session,
) -> None:
    namespaced = _manager(session, namespace="https-")
    plain = _manager(session)

    token = await namespaced.get_token("foo")

    assert not await plain.is_token_valid(token)
    minted = await plain.get_token("foo")
    assert minted.get_value() != token.get_value()


@pytest.mark.anyio
async def test_the_namespace_is_read_per_call(session: Session) -> None:
    prefixes = iter(["https-", "http-"])
    manager = _manager(session, namespace=lambda: next(prefixes))

    _ = await manager.get_token("foo")
    _ = await manager.get_token("bar")

    assert await session.has("_csrf/https-foo")
    assert await session.has("_csrf/http-bar")


@pytest.mark.anyio
async def test_a_token_minted_by_one_manager_checks_out_under_another(session: Session) -> None:
    first = _manager(session)
    second = _manager(session)

    token = await first.get_token("foo")

    assert await second.is_token_valid(token)
