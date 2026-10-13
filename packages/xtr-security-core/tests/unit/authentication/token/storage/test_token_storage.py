"""The token storage holds one token and resets between units of work."""

from __future__ import annotations

import weakref

from xtr_service_contracts import ResetInterface

from xtr_security_core.authentication.token import NullToken
from xtr_security_core.authentication.token.storage import TokenStorage, TokenStorageInterface


def test_it_inherits_its_interfaces() -> None:
    for interface in (TokenStorageInterface, ResetInterface):
        assert interface in TokenStorage.__mro__


def test_starts_empty() -> None:
    assert TokenStorage().get_token() is None


def test_holds_and_clears_a_token() -> None:
    storage = TokenStorage()
    token = NullToken()

    storage.set_token(token)
    assert storage.get_token() is token

    storage.set_token(None)
    assert storage.get_token() is None


def test_reset_forgets_the_token() -> None:
    storage = TokenStorage()
    storage.set_token(NullToken())

    storage.reset()

    assert storage.get_token() is None


def test_can_be_referred_to_weakly() -> None:
    storage = TokenStorage()

    reference = weakref.ref(storage)

    assert reference() is storage


def test_an_initializer_runs_once_on_first_read() -> None:
    storage = TokenStorage()
    token = NullToken()
    calls: list[None] = []

    def initialize() -> None:
        calls.append(None)
        storage.set_token(token)

    storage.set_initializer(initialize)

    assert calls == []
    assert storage.get_token() is token
    assert storage.get_token() is token
    assert len(calls) == 1


def test_storing_a_token_runs_the_pending_initializer_first() -> None:
    storage = TokenStorage()
    stored = NullToken()
    calls: list[None] = []
    storage.set_initializer(lambda: calls.append(None))

    storage.set_token(stored)

    assert calls == [None]
    assert storage.get_token() is stored


def test_clearing_the_token_drops_the_pending_initializer_unrun() -> None:
    storage = TokenStorage()
    calls: list[None] = []
    storage.set_initializer(lambda: calls.append(None))

    storage.set_token(None)

    assert storage.get_token() is None
    assert calls == []


def test_a_cleared_initializer_never_runs() -> None:
    storage = TokenStorage()
    calls: list[None] = []
    storage.set_initializer(lambda: calls.append(None))

    storage.set_initializer(None)

    assert storage.get_token() is None
    assert calls == []


def test_reset_drops_the_pending_initializer() -> None:
    storage = TokenStorage()
    calls: list[None] = []
    storage.set_initializer(lambda: calls.append(None))

    storage.reset()

    assert storage.get_token() is None
    assert calls == []
