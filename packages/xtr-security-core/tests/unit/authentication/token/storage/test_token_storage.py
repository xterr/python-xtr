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
