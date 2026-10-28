"""The signature remember-me handler: a cookie that vouches for itself."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_clock import MockClock
from xtr_security_core.exception import AuthenticationError, UserNotFoundError
from xtr_security_core.signature.signature_hasher import SignatureHasher
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from tests.support.remember_me import RecordingUserProvider
from xtr_security_http._security_state import security_state_of
from xtr_security_http.remember_me import (
    RememberMeCookie,
    RememberMeDetails,
    RememberMeHandlerInterface,
    SignatureRememberMeHandler,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

pytestmark = pytest.mark.anyio

#: Where every test freezes: a moment the expiry arithmetic can be read at.
_FROZEN = "2024-04-09 12:00:00"

#: One year, the lifetime the handler's options default to.
_ONE_YEAR = 31536000

#: A password a test user carries; a fixture, not a secret.
_HASHED = "hashed"

#: The password the same user changes to; still a fixture, still no secret.
_REHASHED = "rehashed"


def _request() -> ServerRequestInterface:
    """Build a request whose state bag is parked, the flow's own contract."""
    bag: dict[str, object] = {}
    return make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)


def _staged_of(request: ServerRequestInterface) -> RememberMeCookie:
    """Return the cookie a handler staged on the request's state."""
    bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
    assert isinstance(bag, dict)
    cookie = security_state_of(cast("dict[str, object]", bag)).attributes.get(
        SecurityRequestAttributes.REMEMBER_ME_COOKIE,
    )
    assert isinstance(cookie, RememberMeCookie)
    return cookie


def _details_of(cookie: RememberMeCookie | None) -> RememberMeDetails:
    """Read a staged cookie's value back into the details it was written from."""
    assert cookie is not None
    assert cookie.value is not None
    return RememberMeDetails.from_raw_cookie(cookie.value)


def _frozen() -> MockClock:
    return MockClock(_FROZEN)


def _handler(
    clock: MockClock,
    user: UserInterface,
) -> tuple[SignatureRememberMeHandler, RecordingUserProvider]:
    """Build the handler over a frozen clock, its user registered with the provider."""
    provider = RecordingUserProvider({user.get_user_identifier(): user})
    hasher = SignatureHasher(["password"], "a-secret", clock=clock)
    return SignatureRememberMeHandler(hasher, provider, clock=clock), provider


def test_the_handler_satisfies_the_interface() -> None:
    handler, _provider = _handler(_frozen(), InMemoryUser("ada", password=_HASHED))

    assert isinstance(handler, RememberMeHandlerInterface)


async def test_create_stages_a_cookie_signed_until_a_lifetime_from_now() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(clock, user)
    request = _request()

    await handler.create_remember_me_cookie(request, user)

    cookie = _staged_of(request)
    assert cookie.name == "REMEMBERME"
    details = _details_of(cookie)
    assert details.get_user_identifier() == "ada"
    assert details.get_expires() == int(clock.now().timestamp()) + _ONE_YEAR
    expected = SignatureHasher(["password"], "a-secret", clock=clock).compute_signature_hash(
        user,
        details.get_expires(),
    )
    assert details.get_value() == expected


async def test_consume_accepts_the_cookie_create_staged_and_reissues_it() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(clock, user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))

    presented = _request()
    loaded = await handler.consume_remember_me_cookie(presented, details)

    assert loaded.get_user_identifier() == "ada"
    fresh = _details_of(_staged_of(presented))
    assert fresh.get_user_identifier() == "ada"
    assert fresh.get_expires() == int(clock.now().timestamp()) + _ONE_YEAR


async def test_consume_refuses_a_tampered_value() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(clock, user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))

    with pytest.raises(AuthenticationError, match="hash is invalid"):
        _ = await handler.consume_remember_me_cookie(_request(), details.with_value("tampered"))


async def test_consume_refuses_an_expired_cookie() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(clock, user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    clock.sleep(_ONE_YEAR + 10)

    with pytest.raises(AuthenticationError, match="expired"):
        _ = await handler.consume_remember_me_cookie(_request(), details)


async def test_consume_refuses_a_cookie_whose_user_changed_their_password() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider = _handler(clock, user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    provider.users["ada"] = InMemoryUser("ada", password=_REHASHED)

    with pytest.raises(AuthenticationError, match="hash is invalid"):
        _ = await handler.consume_remember_me_cookie(_request(), details)


async def test_consume_lets_an_unknown_user_be_the_providers_own_refusal() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider = _handler(clock, user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    provider.users.clear()

    with pytest.raises(UserNotFoundError):
        _ = await handler.consume_remember_me_cookie(_request(), details)


async def test_clear_stages_the_cleared_cookie() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider = _handler(clock, user)
    request = _request()

    await handler.clear_remember_me_cookie(request)

    assert _staged_of(request).value is None


async def test_the_options_name_the_cookie_and_its_attributes() -> None:
    clock = _frozen()
    user = InMemoryUser("ada", password=_HASHED)
    provider = RecordingUserProvider({"ada": user})
    hasher = SignatureHasher(["password"], "a-secret", clock=clock)
    handler = SignatureRememberMeHandler(
        hasher,
        provider,
        {"name": "APP_REMEMBER", "secure": True, "samesite": "lax"},
        clock=clock,
    )
    request = _request()

    await handler.create_remember_me_cookie(request, user)

    cookie = _staged_of(request)
    assert cookie.name == "APP_REMEMBER"
    assert cookie.secure is True
    assert cookie.samesite == "lax"
    assert "secure" in cookie.header_value()
    assert "samesite=lax" in cookie.header_value()
