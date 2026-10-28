"""What a successful login does to the session the request reattached."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_security_core.exception import SecurityError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_csrf import ClearableTokenStorageInterface

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.exception import (
    InvalidSessionStrategyError,
    MissingSessionError,
    MissingStateBagError,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes
from xtr_security_http.session import SessionAuthenticationStrategy

if TYPE_CHECKING:
    from xtr_http_message import ServerRequest
    from xtr_security_core.authentication.token.token_interface import TokenInterface

pytestmark = pytest.mark.anyio


@final
class _RecordingClearableStorage:
    """A clearable CSRF token storage that records the clears it is asked for."""

    __slots__ = ("clears", "tokens")

    def __init__(self) -> None:
        self.clears = 0
        self.tokens: dict[str, str] = {}

    async def get_token(self, token_id: str) -> str:
        return self.tokens[token_id]

    async def set_token(self, token_id: str, token: str) -> None:
        self.tokens[token_id] = token

    async def remove_token(self, token_id: str) -> str | None:
        return self.tokens.pop(token_id, None)

    async def has_token(self, token_id: str) -> bool:
        return token_id in self.tokens

    async def clear(self) -> None:
        self.clears += 1


def test_the_recording_storage_satisfies_the_clearable_interface() -> None:
    assert isinstance(_RecordingClearableStorage(), ClearableTokenStorageInterface)


def test_a_bare_object_does_not_satisfy_the_clearable_interface() -> None:
    assert not isinstance(object(), ClearableTokenStorageInterface)


def _token(identifier: str = "ada") -> TokenInterface:
    return PostAuthenticationToken(InMemoryUser(identifier, roles=()), "main", ())


def _request_with_session() -> tuple[ServerRequest, Session, MemorySessionStorage]:
    """Build a request whose security state carries a saved session with one attribute."""
    storage = MemorySessionStorage()
    session = Session(storage)
    bag: dict[str, object] = {}
    message = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return message, session, storage


async def test_none_leaves_the_session_untouched() -> None:
    message, session, storage = _request_with_session()
    await session.set("kept", "yes")
    await session.save()
    old_id = session.get_id()
    csrf_storage = _RecordingClearableStorage()

    await SessionAuthenticationStrategy(
        SessionAuthenticationStrategy.NONE,
        csrf_storage,
    ).on_authentication(message, _token())

    assert session.get_id() == old_id
    assert await session.get("kept") == "yes"
    assert await storage.read(old_id) == {"kept": "yes"}
    assert csrf_storage.clears == 0


async def test_migrate_carries_the_attributes_to_a_new_id_and_destroys_the_old_entry() -> None:
    message, session, storage = _request_with_session()
    await session.set("kept", "yes")
    await session.save()
    old_id = session.get_id()
    csrf_storage = _RecordingClearableStorage()
    await csrf_storage.set_token("form", "value")

    await SessionAuthenticationStrategy(
        SessionAuthenticationStrategy.MIGRATE,
        csrf_storage,
    ).on_authentication(message, _token())

    assert session.get_id() != old_id
    assert await session.get("kept") == "yes"
    assert await storage.read(old_id) is None
    assert csrf_storage.clears == 1


async def test_migrate_without_a_csrf_storage_rotates_alone() -> None:
    message, session, _storage = _request_with_session()
    await session.set("kept", "yes")
    old_id = session.get_id()

    await SessionAuthenticationStrategy(SessionAuthenticationStrategy.MIGRATE).on_authentication(
        message,
        _token(),
    )

    assert session.get_id() != old_id
    assert await session.get("kept") == "yes"


async def test_invalidate_empties_the_session_and_destroys_the_old_entry() -> None:
    message, session, storage = _request_with_session()
    await session.set("kept", "yes")
    await session.save()
    old_id = session.get_id()
    csrf_storage = _RecordingClearableStorage()

    await SessionAuthenticationStrategy(
        SessionAuthenticationStrategy.INVALIDATE,
        csrf_storage,
    ).on_authentication(message, _token())

    assert session.get_id() != old_id
    assert await session.get("kept") is None
    assert await storage.read(old_id) is None
    assert csrf_storage.clears == 0


async def test_an_unknown_strategy_name_is_a_runtime_error_when_it_runs() -> None:
    message, _session, _storage = _request_with_session()
    strategy = SessionAuthenticationStrategy("bogus")

    with pytest.raises(InvalidSessionStrategyError) as caught:
        await strategy.on_authentication(message, _token())

    assert isinstance(caught.value, RuntimeError)
    assert isinstance(caught.value, SecurityError)
    assert caught.value.get_strategy() == "bogus"
    assert 'Invalid session authentication strategy "bogus"' in str(caught.value)


async def test_a_request_without_a_state_bag_is_refused() -> None:
    message = make_message()

    with pytest.raises(MissingStateBagError):
        await SessionAuthenticationStrategy(
            SessionAuthenticationStrategy.MIGRATE
        ).on_authentication(message, _token())


async def test_a_request_without_a_session_is_refused() -> None:
    message = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, {})

    with pytest.raises(MissingSessionError):
        await SessionAuthenticationStrategy(
            SessionAuthenticationStrategy.MIGRATE
        ).on_authentication(message, _token())
