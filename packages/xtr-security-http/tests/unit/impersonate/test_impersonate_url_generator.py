"""Generating the impersonation and exit paths, URLs and forms."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.switch_user_token import SwitchUserToken
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_csrf.csrf_token import CsrfToken

from tests.support.messages import make_message
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.exception import ImpersonationError
from xtr_security_http.impersonate.impersonate_url_generator import ImpersonateUrlGenerator
from xtr_security_http.impersonate.switch_user_config import SwitchUserConfig
from xtr_security_http.impersonate.switch_user_config_lookup_interface import (
    SwitchUserConfigLookupInterface,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_csrf.csrf_token_manager_interface import CsrfTokenManagerInterface

pytestmark = pytest.mark.anyio


@final
class _FixedLookup:
    """Answers the configuration it was built with, recording every ask."""

    __slots__ = ("_config", "asked")

    def __init__(self, config: SwitchUserConfig | None) -> None:
        self._config = config
        self.asked: list[ServerRequestInterface] = []

    async def get_switch_user_config(
        self,
        request: ServerRequestInterface,
    ) -> SwitchUserConfig | None:
        """Record the request, and answer the configuration this lookup was built with."""
        self.asked.append(request)
        return self._config


@final
class _MintingManager:
    """Mints a stand-in token value under whatever id it is asked for."""

    __slots__ = ("minted",)

    def __init__(self) -> None:
        self.minted: list[str] = []

    async def get_token(self, token_id: str) -> CsrfToken:
        """Mint a stand-in token under ``token_id``."""
        self.minted.append(token_id)
        return CsrfToken(token_id, "minted")

    async def refresh_token(self, token_id: str) -> CsrfToken:
        """Mint a fresh stand-in token under ``token_id``."""
        return CsrfToken(token_id, "minted")

    async def remove_token(self, token_id: str) -> str | None:
        """Answer that nothing was stored under ``token_id``."""
        del token_id
        return None

    async def is_token_valid(self, token: CsrfToken) -> bool:
        """Vouch for any token it minted."""
        return token.get_value() == "minted"


def _generator(
    lookup: _FixedLookup,
    storage: TokenStorage,
    *,
    uri_builder: Callable[[str, ServerRequestInterface | None], str] | None = None,
    csrf_token_manager: CsrfTokenManagerInterface | None = None,
) -> ImpersonateUrlGenerator:
    return ImpersonateUrlGenerator(lookup, storage, uri_builder, csrf_token_manager)


def _impersonated_storage() -> TokenStorage:
    storage = TokenStorage()
    storage.set_token(
        SwitchUserToken(
            InMemoryUser("ada"),
            "main",
            (),
            PostAuthenticationToken(
                InMemoryUser("admin"),
                "main",
                (),
            ),
        ),
    )
    return storage


async def test_the_impersonation_path_carries_the_parameter_on_the_current_page() -> None:
    lookup = _FixedLookup(SwitchUserConfig())
    generator = _generator(lookup, TokenStorage())
    request = make_message(path="/admin", query="page=2")

    path = await generator.generate_impersonation_path(request, "ada")

    assert path == "/admin?page=2&_switch_user=ada"


async def test_the_impersonation_url_goes_through_the_uri_builder() -> None:
    lookup = _FixedLookup(SwitchUserConfig())
    generator = _generator(
        lookup,
        TokenStorage(),
        uri_builder=lambda path, request: f"https://example.com{path}",
    )
    request = make_message(path="/admin")

    url = await generator.generate_impersonation_url(request, "ada")

    assert url == "https://example.com/admin?_switch_user=ada"


async def test_the_impersonation_url_is_the_path_while_no_builder_is_injected() -> None:
    lookup = _FixedLookup(SwitchUserConfig())
    generator = _generator(lookup, TokenStorage())

    url = await generator.generate_impersonation_url(make_message(path="/admin"), "ada")

    assert url == "/admin?_switch_user=ada"


async def test_the_exit_path_is_empty_while_nobody_is_impersonated() -> None:
    lookup = _FixedLookup(SwitchUserConfig())
    generator = _generator(lookup, TokenStorage())

    assert await generator.generate_exit_path(make_message()) == ""


async def test_the_exit_path_carries_the_exit_value_while_impersonated() -> None:
    lookup = _FixedLookup(SwitchUserConfig())
    generator = _generator(lookup, _impersonated_storage())

    path = await generator.generate_exit_path(make_message(path="/admin", query="page=2"))

    assert path == "/admin?page=2&_switch_user=_exit"


async def test_a_target_uri_replaces_the_current_page() -> None:
    lookup = _FixedLookup(SwitchUserConfig())
    generator = _generator(lookup, TokenStorage())

    path = await generator.generate_impersonation_path(
        make_message(path="/admin"),
        "ada",
        "/elsewhere",
    )

    assert path == "/elsewhere?_switch_user=ada"


async def test_a_dedicated_path_carries_the_target_path_explicitly() -> None:
    lookup = _FixedLookup(SwitchUserConfig(path="/switch"))
    generator = _generator(lookup, TokenStorage())
    request = make_message(path="/admin", query="page=2")

    path = await generator.generate_impersonation_path(request, "ada")

    assert path == "/switch?_switch_user=ada&_target_path=%2Fadmin%3Fpage%3D2"


async def test_a_dedicated_path_takes_the_target_uri_over_the_current_page() -> None:
    lookup = _FixedLookup(SwitchUserConfig(path="/switch"))
    generator = _generator(lookup, TokenStorage())

    path = await generator.generate_impersonation_path(
        make_message(path="/admin"),
        "ada",
        "/back",
    )

    assert path == "/switch?_switch_user=ada&_target_path=%2Fback"


async def test_a_switch_asking_for_a_forgery_token_carries_the_minted_token() -> None:
    lookup = _FixedLookup(SwitchUserConfig(enable_csrf=True))
    manager = _MintingManager()
    generator = _generator(lookup, TokenStorage(), csrf_token_manager=manager)

    path = await generator.generate_impersonation_path(make_message(path="/admin"), "ada")

    assert path == "/admin?_switch_user=ada&_csrf_token=minted"
    assert manager.minted == ["switch_user"]


async def test_a_switch_asking_for_a_forgery_token_without_a_manager_is_refused() -> None:
    lookup = _FixedLookup(SwitchUserConfig(enable_csrf=True))
    generator = _generator(lookup, TokenStorage())

    with pytest.raises(ImpersonationError, match="without a CSRF token manager"):
        _ = await generator.generate_impersonation_path(make_message(), "ada")


async def test_a_request_without_a_switch_configuration_is_refused() -> None:
    lookup = _FixedLookup(None)
    generator = _generator(lookup, TokenStorage())

    with pytest.raises(ImpersonationError, match="without a firewall configured"):
        _ = await generator.generate_impersonation_path(make_message(), "ada")


async def test_a_dedicated_path_configured_as_a_route_name_is_refused() -> None:
    lookup = _FixedLookup(SwitchUserConfig(path="switch_route"))
    generator = _generator(lookup, TokenStorage())

    with pytest.raises(ImpersonationError, match="route names"):
        _ = await generator.generate_impersonation_path(make_message(), "ada")


async def test_the_impersonation_form_carries_the_fields_and_the_forgery_field() -> None:
    lookup = _FixedLookup(SwitchUserConfig(enable_csrf=True))
    generator = _generator(lookup, TokenStorage(), csrf_token_manager=_MintingManager())

    form = await generator.generate_impersonation_form(make_message(path="/admin"), "ada")

    assert form["action"] == "/admin"
    assert form["fields"] == {"_switch_user": "ada", "_csrf_token": "minted"}
    assert form["csrf_field"] == "_csrf_token"


async def test_the_exit_form_is_empty_while_nobody_is_impersonated() -> None:
    lookup = _FixedLookup(SwitchUserConfig())
    generator = _generator(lookup, TokenStorage())

    form = await generator.generate_exit_form(make_message())

    assert form["action"] == ""
    assert form["fields"] == {}
    assert form["csrf_field"] is None


async def test_the_exit_form_carries_the_fields_while_impersonated() -> None:
    lookup = _FixedLookup(SwitchUserConfig())
    generator = _generator(lookup, _impersonated_storage())

    form = await generator.generate_exit_form(make_message(path="/admin"))

    assert form["action"] == "/admin"
    assert form["fields"] == {"_switch_user": "_exit"}
    assert form["csrf_field"] is None


async def test_the_configured_parameter_names_are_read_from_the_configuration() -> None:
    lookup = _FixedLookup(SwitchUserConfig(parameter="become"))
    generator = _generator(lookup, TokenStorage())

    path = await generator.generate_impersonation_path(make_message(path="/admin"), "ada")

    assert path == "/admin?become=ada"


async def test_the_lookup_is_asked_about_the_request() -> None:
    lookup = _FixedLookup(SwitchUserConfig())
    generator = _generator(lookup, TokenStorage())
    request = make_message(path="/admin")

    _ = await generator.generate_impersonation_path(request, "ada")

    assert lookup.asked == [request]


def test_the_lookup_satisfies_the_local_interface() -> None:
    assert isinstance(_FixedLookup(None), SwitchUserConfigLookupInterface)
