"""The forgery-token machinery the bundle owns for the csrf package."""

from __future__ import annotations

from collections.abc import Hashable
from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_security_csrf.csrf_token_manager_interface import CsrfTokenManagerInterface
from xtr_security_csrf.token_storage.clearable_token_storage_interface import (
    ClearableTokenStorageInterface,
)
from xtr_security_http._security_state import security_state_of
from xtr_security_http.exception import MissingSessionError
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from tests.support.messages import make_message
from xtr_security.bundle import HttpBasicConfig
from xtr_security.bundle._csrf_wiring import (
    ParkedRequest,
    ParkedSessionTokenStorage,
    firewall_asks_for_csrf,
    form_login_asks_for_csrf,
    register_csrf_token_manager,
)
from xtr_security.bundle.authenticator_configs import FormLoginConfig
from xtr_security.firewall_config import FirewallConfig
from xtr_security.logout_config import LogoutConfig

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ServiceConfigurator
    from xtr_http_message import ServerRequest

pytestmark = pytest.mark.anyio


def _request_parking_a_session() -> tuple[ServerRequest, Session]:
    """Return a request whose state bag carries a parked session, and the session."""
    request = make_message()
    bag: dict[str, object] = {}
    session = Session.from_request(request, MemorySessionStorage())
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return request.with_attribute(SecurityRequestAttributes.STATE_BAG, bag), session


async def test_the_storage_keeps_its_tokens_in_the_session_the_request_parked() -> None:
    request, _session = _request_parking_a_session()
    storage = ParkedSessionTokenStorage(_park_holding(request))

    await storage.set_token("authenticate", "a-value")

    assert await storage.has_token("authenticate")
    assert await storage.get_token("authenticate") == "a-value"
    assert await storage.remove_token("authenticate") == "a-value"
    assert not await storage.has_token("authenticate")


async def test_the_storage_reads_the_session_per_call_not_per_build() -> None:
    """The session is read on every call, so a build before the park still sees it.

    A chain step is built before the chain runs — before the context
    listener has reattached anything — and this is what makes that safe.
    """
    request, _session = _request_parking_a_session()
    park = ParkedRequest()
    storage = ParkedSessionTokenStorage(park)

    park.request = request

    await storage.set_token("authenticate", "a-value")
    assert await storage.has_token("authenticate")


async def test_the_storage_clears_every_token_the_session_minted() -> None:
    request, _session = _request_parking_a_session()
    storage = ParkedSessionTokenStorage(_park_holding(request))
    await storage.set_token("authenticate", "one")
    await storage.set_token("logout", "two")

    await storage.clear()

    assert not await storage.has_token("authenticate")
    assert not await storage.has_token("logout")


async def test_the_storage_refuses_a_request_that_parked_no_session() -> None:
    storage = ParkedSessionTokenStorage(_park_holding(make_message()))

    with pytest.raises(MissingSessionError):
        _ = await storage.has_token("authenticate")


async def test_the_storage_refuses_a_park_no_request_was_handed() -> None:
    storage = ParkedSessionTokenStorage(ParkedRequest())

    with pytest.raises(MissingSessionError):
        _ = await storage.has_token("authenticate")


def _park_holding(request: ServerRequest) -> ParkedRequest:
    """Return a park carrying ``request``, as the parking listener would leave it."""
    park = ParkedRequest()
    park.request = request
    return park


@final
class _RecordingConfigurator:
    """A stand-in configurator recording every ``set`` and ``alias``."""

    def __init__(self) -> None:
        self.set_targets: list[Callable[..., object]] = []
        self.aliases: list[type] = []
        self.loaded: list[str] = []

    def set(
        self,
        target: Callable[..., object],
        /,
        *,
        qualifier: Hashable | None = None,
        lifetime: object | None = None,
    ) -> object:
        del qualifier, lifetime
        self.set_targets.append(target)
        return cast("object", self)

    def alias(self, alias: type, target: type, /, **qualifiers: object) -> None:
        del target, qualifiers
        self.aliases.append(alias)

    def load(self, *modules: str) -> None:
        """Record the listener module the registration asks the scan to find."""
        self.loaded.extend(modules)


def test_the_manager_registers_the_storages_interface_and_its_own() -> None:
    services = _RecordingConfigurator()

    register_csrf_token_manager(cast("ServiceConfigurator", cast("object", services)))

    assert services.aliases == [ClearableTokenStorageInterface, CsrfTokenManagerInterface]
    assert services.loaded == ["xtr_security.bundle._csrf_listeners"]
    _park_factory, storage_factory, manager_factory = services.set_targets
    assert storage_factory.__annotations__["return"] is ParkedSessionTokenStorage
    assert manager_factory.__annotations__["storage"] is ClearableTokenStorageInterface


def test_a_firewall_asks_through_its_form_login_its_logout_or_both() -> None:
    assert firewall_asks_for_csrf(
        FirewallConfig(authenticators=(FormLoginConfig(login_path="/login", enable_csrf=True),))
    )
    assert firewall_asks_for_csrf(
        FirewallConfig(authenticators=(_an_authenticator(),), logout=LogoutConfig(enable_csrf=True))
    )
    assert firewall_asks_for_csrf(
        FirewallConfig(
            authenticators=(_an_authenticator(),),
            logout=LogoutConfig(clear_csrf_tokens=True),
        )
    )
    assert not firewall_asks_for_csrf(
        FirewallConfig(authenticators=(FormLoginConfig(login_path="/login"),))
    )
    assert not firewall_asks_for_csrf(FirewallConfig(authenticators=(_an_authenticator(),)))


def test_a_form_login_asks_only_when_its_form_carries_a_token() -> None:
    assert form_login_asks_for_csrf(
        FirewallConfig(authenticators=(FormLoginConfig(login_path="/login", enable_csrf=True),))
    )
    assert not form_login_asks_for_csrf(
        FirewallConfig(authenticators=(FormLoginConfig(login_path="/login"),))
    )


def _an_authenticator() -> object:
    """A configured authenticator that asks for no forgery token."""
    return HttpBasicConfig()
