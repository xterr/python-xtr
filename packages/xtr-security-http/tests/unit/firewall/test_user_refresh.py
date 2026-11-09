"""The provider loop that reloads a session token's user."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

import pytest
from typing_extensions import override
from xtr_security_core.exception import UnsupportedUserError, UserNotFoundError
from xtr_security_core.user.equatable_interface import EquatableInterface
from xtr_security_core.user.password_digest import password_digest
from xtr_security_core.user.session_serializable_user_interface import (
    SessionSerializableUserInterface,
)

from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.firewall._user_refresh import UserRefresher
from xtr_security_http.session import PasswordSessionUser, SessionTokenSerializer, SessionUser

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_security_core.user.user_interface import UserInterface

pytestmark = pytest.mark.anyio


@final
class _PlainPasswordUser:
    """A password-carrying user that keeps no state of its own in a session."""

    def __init__(
        self,
        identifier: str,
        password: str | None = None,
        roles: Sequence[str] = ("ROLE_USER",),
    ) -> None:
        self._identifier = identifier
        self._password = password
        self._roles = tuple(roles)

    def get_user_identifier(self) -> str:
        return self._identifier

    def get_roles(self) -> tuple[str, ...]:
        return self._roles

    def get_password(self) -> str | None:
        return self._password


@final
class _LoadingProvider:
    """Loads users by identifier from a table, and fails the test when asked to refresh one."""

    def __init__(
        self,
        users: Mapping[str, UserInterface] | None = None,
        *,
        supports: bool = True,
        error: Exception | None = None,
    ) -> None:
        self._users = dict(users or {})
        self._supports = supports
        self._error = error
        self.loaded: list[str] = []

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        self.loaded.append(identifier)
        if self._error is not None:
            raise self._error
        return self._users[identifier]

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        raise AssertionError(f"A stand-in reached refresh_user: {user!r}.")

    def supports_class(self, user_class: type) -> bool:
        del user_class
        return self._supports


@final
class _RefreshingProvider:
    """Refreshes every user into the one it was built with, recording what it was handed."""

    def __init__(self, refreshed: UserInterface) -> None:
        self._refreshed = refreshed
        self.handed: list[UserInterface] = []

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        raise AssertionError(f"A user kept whole was loaded by its identifier: {identifier}.")

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        self.handed.append(user)
        return self._refreshed

    def supports_class(self, user_class: type) -> bool:
        del user_class
        return True


@final
class _VerdictUser(SessionSerializableUserInterface, EquatableInterface):
    """A user kept whole that compares itself, answering the verdict it was kept with."""

    def __init__(self, *, same: bool) -> None:
        self._same = same

    @override
    def get_user_identifier(self) -> str:
        return "ada"

    @override
    def get_roles(self) -> tuple[str, ...]:
        return ("ROLE_USER",)

    @override
    def is_equal_to(self, user: UserInterface) -> bool:
        del user
        return self._same

    @override
    def to_session(self) -> Mapping[str, object]:
        return {"same": self._same}

    @classmethod
    @override
    def from_session(cls, state: Mapping[str, object]) -> Self:
        same = state.get("same")
        assert isinstance(same, bool)
        return cls(same=same)


@final
class _DetachableUser:
    """A user that, like a record its unit of work let go of, fails every read once detached."""

    def __init__(self, identifier: str) -> None:
        self._identifier = identifier
        self.detached = False

    def get_user_identifier(self) -> str:
        self._ensure_attached()
        return self._identifier

    def get_roles(self) -> tuple[str, ...]:
        self._ensure_attached()
        return ("ROLE_USER",)

    def get_password(self) -> str | None:
        self._ensure_attached()
        return "hashed"

    def _ensure_attached(self) -> None:
        if self.detached:
            raise AssertionError("A user its request let go of was read.")


def _token(user: UserInterface, roles: tuple[str, ...] = ("ROLE_USER",)) -> PostAuthenticationToken:
    return PostAuthenticationToken(user, "main", roles)


def _stand_in(password: str) -> PasswordSessionUser:
    return PasswordSessionUser("ada", ["ROLE_USER"], password_digest(password))


async def test_a_stand_in_is_reloaded_by_its_identifier_and_never_refreshed() -> None:
    reloaded = _PlainPasswordUser("ada", "hash-1")
    provider = _LoadingProvider({"ada": reloaded})
    stand_in = _stand_in("hash-1")

    result = await UserRefresher((provider,)).refresh(_token(stand_in), stand_in)

    assert result.token is not None
    assert result.token.get_user() is reloaded
    assert provider.loaded == ["ada"]


async def test_a_stand_in_whose_password_did_not_change_stays_signed_in() -> None:
    provider = _LoadingProvider({"ada": _PlainPasswordUser("ada", "hash-1")})
    stand_in = _stand_in("hash-1")

    result = await UserRefresher((provider,)).refresh(_token(stand_in), stand_in)

    assert result.token is not None


async def test_a_stand_in_whose_password_changed_is_deauthenticated() -> None:
    provider = _LoadingProvider({"ada": _PlainPasswordUser("ada", "hash-2")})
    stand_in = _stand_in("hash-1")

    result = await UserRefresher((provider,)).refresh(_token(stand_in), stand_in)

    assert result.token is None
    assert result.deauthentication_reason == "the user has changed"
    assert result.provider_classes == (_LoadingProvider,)


async def test_a_stand_in_whose_roles_changed_is_deauthenticated() -> None:
    reloaded = _PlainPasswordUser("ada", "hash-1", roles=("ROLE_USER", "ROLE_ADMIN"))
    provider = _LoadingProvider({"ada": reloaded})
    stand_in = _stand_in("hash-1")

    result = await UserRefresher((provider,)).refresh(_token(stand_in), stand_in)

    assert result.token is None


async def test_a_stand_in_that_stopped_carrying_a_password_is_deauthenticated() -> None:
    """The plain stand-in carries no password, so a reload that carries one has changed."""
    provider = _LoadingProvider({"ada": _PlainPasswordUser("ada", "hash-1")})
    stand_in = SessionUser("ada", ["ROLE_USER"])

    result = await UserRefresher((provider,)).refresh(_token(stand_in), stand_in)

    assert result.token is None


async def test_a_provider_loading_a_class_it_does_not_support_is_skipped() -> None:
    passing = _LoadingProvider({"ada": _PlainPasswordUser("ada", "hash-1")}, supports=False)
    reloaded = _PlainPasswordUser("ada", "hash-1")
    answering = _LoadingProvider({"ada": reloaded})
    stand_in = _stand_in("hash-1")

    result = await UserRefresher((passing, answering)).refresh(_token(stand_in), stand_in)

    assert result.token is not None
    assert result.token.get_user() is reloaded


async def test_a_provider_refusing_the_stand_in_hands_it_to_the_next() -> None:
    refusing = _LoadingProvider(error=UnsupportedUserError("Not mine."))
    reloaded = _PlainPasswordUser("ada", "hash-1")
    answering = _LoadingProvider({"ada": reloaded})
    stand_in = _stand_in("hash-1")

    result = await UserRefresher((refusing, answering)).refresh(_token(stand_in), stand_in)

    assert result.token is not None
    assert result.token.get_user() is reloaded


async def test_a_stand_in_no_provider_finds_is_deauthenticated() -> None:
    provider = _LoadingProvider(error=UserNotFoundError("ada"))
    stand_in = _stand_in("hash-1")

    result = await UserRefresher((provider,)).refresh(_token(stand_in), stand_in)

    assert result.token is None
    assert result.deauthentication_reason == "the user could not be found by any user provider"
    assert result.provider_classes == (_LoadingProvider,)


async def test_a_stand_in_no_provider_loads_as_a_class_it_supports_is_refused() -> None:
    provider = _LoadingProvider({"ada": _PlainPasswordUser("ada", "hash-1")}, supports=False)
    stand_in = _stand_in("hash-1")

    with pytest.raises(UnsupportedUserError, match="the session token carries"):
        _ = await UserRefresher((provider,)).refresh(_token(stand_in), stand_in)


@pytest.mark.parametrize("same", [True, False])
async def test_a_user_kept_whole_that_compares_itself_decides(same: bool) -> None:
    """The reload's other roles would deauthenticate — unless the user says it is the same."""
    kept = _VerdictUser(same=same)
    provider = _RefreshingProvider(_PlainPasswordUser("ada", roles=("ROLE_ADMIN",)))

    result = await UserRefresher((provider,)).refresh(_token(kept), kept)

    assert (result.token is not None) is same
    assert provider.handed == [kept]


async def test_a_user_its_request_let_go_of_still_authenticates_on_the_next_request() -> None:
    """Only the snapshot was kept, so the next request never reads the detached user."""
    user = _DetachableUser("ada")
    serializer = SessionTokenSerializer()
    kept = serializer.encode(_token(user))  # the response half, while the user is attached
    user.detached = True  # the request is over, and its unit of work let the user go
    restored = serializer.decode(kept)
    assert restored is not None
    stand_in = restored.get_user()
    assert stand_in is not None
    provider = _LoadingProvider({"ada": _DetachableUser("ada")})

    result = await UserRefresher((provider,)).refresh(restored, stand_in)

    assert result.token is not None
    assert result.token.get_user_identifier() == "ada"
