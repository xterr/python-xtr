"""Generating the logout path, URL and form of a registered firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_csrf import CsrfTokenManagerInterface
from xtr_security_csrf.csrf_token import CsrfToken

from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.logout import LogoutUrlGenerator

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

pytestmark = pytest.mark.anyio


@final
class _RecordingManager:
    """A cross-site request forgery manager that mints the value it was built with."""

    __slots__ = ("_value", "asked")

    def __init__(self, value: str = "minted") -> None:
        self._value = value
        self.asked: list[str] = []

    async def get_token(self, token_id: str) -> CsrfToken:
        """Record the id, and mint this manager's value under it."""
        self.asked.append(token_id)
        return CsrfToken(token_id, self._value)

    async def refresh_token(self, token_id: str) -> CsrfToken:
        """Mint a fresh value; the generator never refreshes."""
        return CsrfToken(token_id, "refreshed")

    async def remove_token(self, token_id: str) -> str | None:
        """Drop the token; the generator never removes."""
        del token_id
        return None

    async def is_token_valid(self, token: CsrfToken) -> bool:
        """Vouch for nothing; the generator never checks."""
        del token
        return False


@final
class _RecordingTokenStorage:
    """A token storage that answers what it was set, recording every set."""

    __slots__ = ("_token", "sets")

    def __init__(self, token: TokenInterface | None = None) -> None:
        self._token = token
        self.sets: list[TokenInterface | None] = []

    def get_token(self) -> TokenInterface | None:
        """Return the token this storage was built with, or last set to."""
        return self._token

    def set_token(self, token: TokenInterface | None) -> None:
        """Record the set, and answer it from now on."""
        self._token = token
        self.sets.append(token)


def _token(firewall_name: str = "main") -> PostAuthenticationToken:
    return PostAuthenticationToken(InMemoryUser("ada", roles=()), firewall_name, ())


def test_the_recording_manager_satisfies_the_manager_interface() -> None:
    assert isinstance(_RecordingManager(), CsrfTokenManagerInterface)


async def test_a_registered_firewall_generates_its_logout_path_by_key() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "/logout", None, None)

    assert await generator.get_logout_path("main") == "/logout"


async def test_a_registered_absolute_url_is_generated_as_it_is() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "https://example.com/logout", None, None)

    assert await generator.get_logout_path("main") == "https://example.com/logout"
    assert await generator.get_logout_url("main") == "https://example.com/logout"


async def test_an_unknown_key_is_refused() -> None:
    generator = LogoutUrlGenerator()

    with pytest.raises(InvalidArgumentError) as caught:
        _ = await generator.get_logout_path("nope")

    assert 'No logout listener is registered for the firewall "nope"' in str(caught.value)


async def test_a_keyless_generation_resolves_the_firewall_the_token_names() -> None:
    generator = LogoutUrlGenerator(token_storage=_RecordingTokenStorage(_token("main")))
    generator.register_listener("main", "/main/logout", None, None)
    generator.register_listener("api", "/api/logout", None, None)

    assert await generator.get_logout_path() == "/main/logout"


async def test_a_token_of_a_kind_without_a_firewall_name_resolves_nothing() -> None:
    generator = LogoutUrlGenerator(token_storage=_RecordingTokenStorage())

    with pytest.raises(InvalidArgumentError):
        _ = await generator.get_logout_path()


async def test_a_keyless_generation_resolves_the_current_firewall() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "/main/logout", None, None)
    generator.set_current_firewall("main")

    assert await generator.get_logout_path() == "/main/logout"


async def test_a_keyless_generation_resolves_the_current_context() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "/main/logout", None, None, context="shared")
    generator.register_listener("api", "/api/logout", None, None)
    generator.set_current_firewall(context="shared")

    assert await generator.get_logout_path() == "/main/logout"


async def test_the_token_names_the_firewall_ahead_of_the_current_one() -> None:
    generator = LogoutUrlGenerator(token_storage=_RecordingTokenStorage(_token("main")))
    generator.register_listener("main", "/main/logout", None, None)
    generator.register_listener("api", "/api/logout", None, None)
    generator.set_current_firewall("api")

    assert await generator.get_logout_path() == "/main/logout"


async def test_a_keyless_generation_behind_no_firewall_is_refused() -> None:
    generator = LogoutUrlGenerator()

    with pytest.raises(InvalidArgumentError) as caught:
        _ = await generator.get_logout_path()

    assert "not behind a firewall" in str(caught.value)


async def test_a_keyless_generation_the_current_firewall_did_not_register_is_refused() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "/main/logout", None, None)
    generator.set_current_firewall("other")

    with pytest.raises(InvalidArgumentError) as caught:
        _ = await generator.get_logout_path()

    assert "Unable to find a logout listener for the current firewall" in str(caught.value)


async def test_reset_puts_the_current_firewall_tracking_back_to_none() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "/main/logout", None, None)
    generator.set_current_firewall("main")
    generator.reset()

    with pytest.raises(InvalidArgumentError):
        _ = await generator.get_logout_path()


async def test_the_logout_url_runs_the_path_through_the_uri_builder() -> None:
    generator = LogoutUrlGenerator(uri_builder=lambda path: f"https://example.com{path}")
    generator.register_listener("main", "/logout", None, None)

    assert await generator.get_logout_url("main") == "https://example.com/logout"


async def test_the_logout_url_without_a_builder_is_the_path_itself() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "/logout", None, None)

    assert await generator.get_logout_url("main") == "/logout"


async def test_a_forgery_token_rides_the_generated_path_as_a_query() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "/logout", "logout", "_csrf_token", _RecordingManager())

    assert await generator.get_logout_path("main") == "/logout?_csrf_token=minted"


async def test_a_forgery_token_rides_the_generated_url_as_a_query() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "/logout", "logout", "_csrf_token", _RecordingManager())

    assert await generator.get_logout_url("main") == "/logout?_csrf_token=minted"


async def test_a_forgery_token_rides_a_url_that_already_carries_a_query_behind_an_ampersand() -> (
    None
):
    generator = LogoutUrlGenerator()
    generator.register_listener(
        "main", "/logout?from=nav", "logout", "_csrf_token", _RecordingManager()
    )

    assert await generator.get_logout_path("main") == "/logout?from=nav&_csrf_token=minted"


async def test_the_form_carries_the_forgery_token_as_a_hidden_field() -> None:
    manager = _RecordingManager()
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "/logout", "logout", "_csrf_token", manager)

    form = await generator.get_logout_form("main")

    assert form == {
        "action": "/logout",
        "fields": {"_csrf_token": "minted"},
        "csrf_field": "_csrf_token",
    }
    assert manager.asked == ["logout"]


async def test_the_form_of_a_logout_without_a_manager_carries_no_fields() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "/logout", None, None)

    form = await generator.get_logout_form("main")

    assert form == {"action": "/logout", "fields": {}, "csrf_field": None}


async def test_a_route_name_is_refused_as_a_logout_path() -> None:
    generator = LogoutUrlGenerator()
    generator.register_listener("main", "app_logout", None, None)

    with pytest.raises(InvalidArgumentError) as caught:
        _ = await generator.get_logout_url("main")

    assert "route names are not supported" in str(caught.value)
