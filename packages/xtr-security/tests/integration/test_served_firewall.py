"""The security bundle over a real served FastAPI application.

Drives the served fixture through ``httpx.ASGITransport`` inside the app's own
lifespan — never ``TestClient`` — so ``setup(app, kernel)`` builds and boots the
kernel per life. Covers the whole request surface: challenges, tokens, roles,
scopes, public and open firewalls, events, the OpenAPI schema, ``CurrentUser``,
``IsGranted`` in every shape, and concurrent isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import anyio
import httpx
import pytest
from xtr_password_hasher import PlaintextPasswordHasher

from tests.fixtures.security_app import listeners
from tests.fixtures.security_app.app import app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Hashable, Mapping

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Serve the fixture app inside its lifespan, cleared of recorded events."""
    listeners.EVENTS.clear()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as opened:
            yield opened


async def test_no_token_is_challenged(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Bearer realm="api"'


async def test_an_unknown_token_is_an_invalid_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me", headers={"authorization": "Bearer nope"})

    assert response.status_code == 401
    assert response.json() == {"error": "invalid_token"}
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


async def test_a_good_token_is_authenticated(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me", headers={"authorization": "Bearer good"})

    assert response.status_code == 200
    assert response.json() == {"user": "alice"}


async def test_a_missing_role_is_forbidden(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/admin/panel", headers={"authorization": "Bearer good"})

    assert response.status_code == 403


async def test_a_held_role_is_granted(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/admin/panel", headers={"authorization": "Bearer admin"})

    assert response.status_code == 200
    assert response.json() == {"status": "admin"}


async def test_a_held_scope_passes(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/books", headers={"authorization": "Bearer good"})

    assert response.status_code == 200


async def test_a_missing_scope_is_insufficient(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/reports", headers={"authorization": "Bearer good"})

    assert response.status_code == 403
    challenge = response.headers["www-authenticate"]
    assert 'error="insufficient_scope"' in challenge
    assert 'scope="reports:write"' in challenge


async def test_a_public_access_rule_lets_an_anonymous_request_through(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/public/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "public"}


async def test_a_security_false_firewall_lets_every_request_through(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/open/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "open"}


async def test_current_user_resolves_the_authenticated_user(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me", headers={"authorization": "Bearer admin"})

    assert response.status_code == 200
    assert response.json() == {"user": "root"}


async def test_is_granted_decorator_guards_a_route(client: httpx.AsyncClient) -> None:
    denied = await client.delete("/api/books/1", headers={"authorization": "Bearer good"})
    granted = await client.delete("/api/books/1", headers={"authorization": "Bearer admin"})

    assert denied.status_code == 403
    assert granted.status_code == 200


async def test_is_granted_dependency_guards_a_route(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/admin/panel", headers={"authorization": "Bearer admin"})

    assert response.status_code == 200


async def test_is_granted_callable_over_a_subject(client: httpx.AsyncClient) -> None:
    owned = await client.put("/api/books/owned", headers={"authorization": "Bearer good"})
    other = await client.put("/api/books/other", headers={"authorization": "Bearer good"})

    assert owned.status_code == 200
    assert other.status_code == 403


async def test_events_fire_in_order_on_a_global_listener(client: httpx.AsyncClient) -> None:
    _ = await client.get("/api/me", headers={"authorization": "Bearer good"})

    assert "check_passport" in listeners.EVENTS
    assert "login_success" in listeners.EVENTS
    assert listeners.EVENTS.index("check_passport") < listeners.EVENTS.index("login_success")


async def test_the_firewall_dispatcher_orders_its_listeners_and_merges_the_global() -> None:
    from xtr_dependency_injection import Kernel, unit_of_work
    from xtr_dependency_injection.testing import boot_for_test
    from xtr_event_dispatcher import EventDispatcher
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_security_http.event.check_passport_event import CheckPassportEvent

    from tests.fixtures.security_app.bundles import BUNDLES

    kernel = Kernel(
        "tests.fixtures.security_app",
        env="test",
        bundles=BUNDLES,
        concurrent_scoped_access=True,
    )
    async with await boot_for_test(kernel) as booted, unit_of_work(booted.container) as unit:
        dispatcher = cast("EventDispatcher", await unit.get(EventDispatcherInterface, "api"))
        names = [
            _listener_name(listener) for listener in dispatcher.get_listeners(CheckPassportEvent)
        ]

    assert names.index("UserProviderListener.check_passport") < names.index(
        "CheckCredentialsListener.resolve_user"
    )
    assert names.index("CheckCredentialsListener.resolve_user") < names.index(
        "UserCheckerListener.pre_check_credentials"
    )
    assert names.index("UserCheckerListener.pre_check_credentials") < names.index(
        "CheckCredentialsListener.check_passport"
    )
    assert "record_check_passport" in names


def _listener_name(listener: object) -> str:
    """Name a listener by its owning subscriber's class and method, or the function it is."""
    owner: object = getattr(listener, "__self__", None)
    method: object = getattr(listener, "__name__", None)
    if owner is not None:
        base = type(owner).__name__
        return f"{base}.{method}" if isinstance(method, str) else base
    return method if isinstance(method, str) else repr(listener)


@final
class _SpyDummyHasher:
    """A dummy timing-guard hasher that counts how often its verify is burned."""

    def __init__(self) -> None:
        self._inner = PlaintextPasswordHasher()
        self.verify_calls = 0

    def hash(self, plain: str) -> str:
        return self._inner.hash(plain)

    def verify(self, hashed: str, plain: str) -> bool:
        self.verify_calls += 1
        return self._inner.verify(hashed, plain)

    def needs_rehash(self, hashed: str) -> bool:
        return self._inner.needs_rehash(hashed)


async def test_an_unknown_user_with_a_password_burns_a_dummy_through_the_dispatcher() -> None:
    from xtr_dependency_injection import Kernel, unit_of_work
    from xtr_dependency_injection.testing import boot_for_test
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_password_hasher import PasswordHasherInterface
    from xtr_security_core.exception import BadCredentialsError, UserNotFoundError
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_http import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
    from xtr_security_http.authenticator.passport.credentials.password_credentials import (
        PasswordCredentials,
    )
    from xtr_security_http.authenticator.passport.passport import Passport
    from xtr_security_http.event.check_passport_event import CheckPassportEvent

    from tests.fixtures.security_app.bundles import BUNDLES
    from xtr_security.bundle._wiring import DUMMY_PASSWORD_HASHER_QUALIFIER

    def unknown_loader(identifier: str) -> UserInterface:
        raise UserNotFoundError(user_identifier=identifier)

    spy = _SpyDummyHasher()
    kernel = Kernel(
        "tests.fixtures.security_app",
        env="test",
        bundles=BUNDLES,
        concurrent_scoped_access=True,
    )
    overrides: Mapping[type | tuple[type, Hashable], object] = {
        (PasswordHasherInterface, DUMMY_PASSWORD_HASHER_QUALIFIER): spy
    }
    async with (
        await boot_for_test(kernel, overrides=overrides) as booted,
        unit_of_work(booted.container) as unit,
    ):
        dispatcher = await unit.get(EventDispatcherInterface, "api")
        passport = Passport(
            UserBadge("ghost", user_loader=unknown_loader),
            [PasswordCredentials("secret")],
        )
        event = CheckPassportEvent(cast("AuthenticatorInterface", cast("object", None)), passport)

        with pytest.raises(BadCredentialsError):
            _ = await dispatcher.dispatch(event)

    assert spy.verify_calls == 1


async def test_one_check_passport_event_with_app_and_route_firewalls(
    client: httpx.AsyncClient,
) -> None:
    _ = await client.get("/api/books", headers={"authorization": "Bearer good"})

    assert listeners.EVENTS.count("check_passport") == 1


async def test_the_openapi_schema_lists_the_firewall_schemes_and_scopes(
    client: httpx.AsyncClient,
) -> None:
    schema = cast("Mapping[str, object]", (await client.get("/openapi.json")).json())

    components = cast("Mapping[str, object]", schema["components"])
    schemes = cast("Mapping[str, object]", components["securitySchemes"])
    assert "api" in schemes
    assert cast("Mapping[str, object]", schemes["api"])["scheme"] == "bearer"
    paths = cast("Mapping[str, object]", schema["paths"])
    books_get = cast(
        "Mapping[str, object]", cast("Mapping[str, object]", paths["/api/books"])["get"]
    )
    assert {"api": ["books:read"]} in cast("list[object]", books_get["security"])


async def test_concurrent_requests_stay_isolated(client: httpx.AsyncClient) -> None:
    results: dict[str, int] = {}

    async def call(token: str, expected_key: str) -> None:
        response = await client.get("/api/me", headers={"authorization": f"Bearer {token}"})
        results[expected_key] = response.status_code

    async with anyio.create_task_group() as group:
        for token, key in (("good", "good"), ("admin", "admin"), ("nope", "nope")):
            group.start_soon(call, token, key)  # pyright: ignore[reportUnusedCallResult]  # start_soon returns a handle we do not track

    assert results == {"good": 200, "admin": 200, "nope": 401}
