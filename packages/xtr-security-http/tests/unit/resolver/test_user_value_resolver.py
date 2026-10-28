"""The user value resolver reads the marker's statement against the token storage."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.exception import (
    AuthenticationCredentialsNotFoundError,
    UnsupportedUserError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.decorator.current_user import CurrentUser
from xtr_security_http.resolver.user_value_resolver import UserValueResolver

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.user.user_interface import UserInterface

pytestmark = pytest.mark.anyio


@final
class OtherUser:
    """A user of another class, for the type-match rules."""

    def get_roles(self) -> Sequence[str]:
        """Return no roles; the class is what the tests read."""
        return ()

    def get_user_identifier(self) -> str:
        """Return an identifier; the class is what the tests read."""
        return "other"


def _storage_with(user: UserInterface | None) -> TokenStorage:
    """Return a token storage holding a token over ``user``, or none."""
    storage = TokenStorage()
    if user is not None:
        storage.set_token(UsernamePasswordToken(user, "api", []))
    return storage


async def test_it_returns_none_when_optional_and_anonymous() -> None:
    assert await UserValueResolver(TokenStorage()).resolve(CurrentUser(optional=True)) is None


async def test_it_raises_when_required_and_anonymous() -> None:
    with pytest.raises(AuthenticationCredentialsNotFoundError):
        _ = await UserValueResolver(TokenStorage()).resolve(CurrentUser())


async def test_it_returns_the_authenticated_user() -> None:
    user = InMemoryUser("ada", roles=["ROLE_USER"])
    resolver = UserValueResolver(_storage_with(user))

    assert await resolver.resolve(CurrentUser()) is user


async def test_it_accepts_any_user_class_when_none_is_stated() -> None:
    user = OtherUser()
    resolver = UserValueResolver(_storage_with(user))

    assert await resolver.resolve(CurrentUser()) is user


async def test_it_accepts_a_user_of_a_stated_class() -> None:
    user = InMemoryUser("ada", roles=[])
    resolver = UserValueResolver(_storage_with(user))

    assert await resolver.resolve(CurrentUser(InMemoryUser)) is user


async def test_it_accepts_a_user_of_any_class_in_a_stated_union() -> None:
    user = OtherUser()
    resolver = UserValueResolver(_storage_with(user))

    assert await resolver.resolve(CurrentUser((InMemoryUser, OtherUser))) is user


async def test_it_raises_when_the_user_is_of_another_class() -> None:
    resolver = UserValueResolver(_storage_with(InMemoryUser("ada", roles=[])))

    with pytest.raises(UnsupportedUserError) as caught:
        _ = await resolver.resolve(CurrentUser(OtherUser))

    assert "OtherUser" in str(caught.value)


async def test_it_raises_when_the_user_matches_no_class_in_a_stated_union() -> None:
    resolver = UserValueResolver(_storage_with(OtherUser()))

    with pytest.raises(UnsupportedUserError) as caught:
        _ = await resolver.resolve(CurrentUser((InMemoryUser,)))

    assert "InMemoryUser" in str(caught.value)
