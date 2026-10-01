"""The user badge names an identifier and loads its user once."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_security_core.exception import (
    AuthenticationServiceError,
    BadCredentialsError,
    InvalidArgumentError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.authenticator.passport.badge.user_badge import (
    MAX_USERNAME_LENGTH,
    UserBadge,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_security_core.user.user_interface import UserInterface

pytestmark = pytest.mark.anyio


def test_it_keeps_the_identifier_and_attributes() -> None:
    badge = UserBadge("alice", attributes={"scope": ["a"]})

    assert badge.get_user_identifier() == "alice"
    assert badge.get_attributes() == {"scope": ["a"]}


def _normalize(value: str) -> str:
    return value.strip().lower()


def _load_non_user(identifier: str) -> object:
    del identifier
    return object()


def test_it_normalizes_the_identifier() -> None:
    badge = UserBadge("  Alice  ", identifier_normalizer=_normalize)

    assert badge.get_user_identifier() == "alice"


def test_an_empty_identifier_is_refused() -> None:
    with pytest.raises(BadCredentialsError):
        _ = UserBadge("")


def test_an_over_long_identifier_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = UserBadge("x" * (MAX_USERNAME_LENGTH + 1))


def test_it_is_unresolved_without_a_loader_and_resolves_with_one() -> None:
    badge = UserBadge("alice")

    assert badge.is_resolved() is False
    badge.set_user_loader(InMemoryUser)
    assert badge.is_resolved() is True


async def test_it_loads_the_user_through_a_sync_loader() -> None:
    badge = UserBadge("alice", user_loader=InMemoryUser)

    user = await badge.get_user()

    assert user.get_user_identifier() == "alice"


async def test_it_loads_the_user_through_an_async_loader_once() -> None:
    calls: list[str] = []

    async def loader(identifier: str) -> InMemoryUser:
        calls.append(identifier)
        return InMemoryUser(identifier)

    badge = UserBadge("alice", user_loader=loader)

    first = await badge.get_user()
    second = await badge.get_user()

    assert first is second
    assert calls == ["alice"]


async def test_a_two_argument_loader_receives_the_attributes() -> None:
    seen: dict[str, object] = {}

    def loader(identifier: str, attributes: dict[str, object]) -> InMemoryUser:
        seen.update(attributes)
        return InMemoryUser(identifier)

    badge = UserBadge("alice", user_loader=loader, attributes={"sub": "alice"})

    _ = await badge.get_user()

    assert seen == {"sub": "alice"}


async def test_loading_without_a_loader_is_a_service_error() -> None:
    badge = UserBadge("alice")

    with pytest.raises(AuthenticationServiceError):
        _ = await badge.get_user()


async def test_a_loader_returning_a_non_user_is_a_service_error() -> None:
    # A deliberately wrong loader — typed as one, returning a non-user at runtime.
    wrong_loader = cast("Callable[[str], UserInterface]", cast("object", _load_non_user))
    badge = UserBadge("alice", user_loader=wrong_loader)

    with pytest.raises(AuthenticationServiceError):
        _ = await badge.get_user()


async def test_the_loaded_user_is_readable_without_io() -> None:
    badge = UserBadge("alice", user_loader=InMemoryUser)

    _ = await badge.get_user()

    assert badge.get_loaded_user().get_user_identifier() == "alice"


def test_reading_a_user_before_loading_is_a_service_error() -> None:
    badge = UserBadge("alice")

    with pytest.raises(AuthenticationServiceError):
        _ = badge.get_loaded_user()


def test_the_loader_is_readable() -> None:
    loader = InMemoryUser
    badge = UserBadge("alice", user_loader=loader)

    assert badge.get_user_loader() is loader
