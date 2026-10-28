"""The persistent remember-me handler: a stored series, rotated as it is used."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_clock import MockClock
from xtr_security_core.exception import AuthenticationError, CookieTheftError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from tests.support.remember_me import (
    RecordingTokenProvider,
    RecordingTokenVerifier,
    RecordingUserProvider,
)
from xtr_security_http._security_state import security_state_of
from xtr_security_http.remember_me import (
    PersistentRememberMeHandler,
    RememberMeCookie,
    RememberMeDetails,
    RememberMeHandlerInterface,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from datetime import datetime

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.remember_me.persistent_token import PersistentToken
    from xtr_security_core.user.user_interface import UserInterface

pytestmark = pytest.mark.anyio

#: Where every test freezes, before it moves the clock.
_FROZEN = "2024-04-09 12:00:00"

#: One year, the lifetime the handler's options default to.
_ONE_YEAR = 31536000

#: The rotation window: a value used again within it is the same request twice.
_WINDOW = 60

#: A password a test user carries; a fixture, not a secret.
_HASHED = "hashed"

#: The password the same user changes to; still a fixture, still no secret.
_REHASHED = "rehashed"


@final
class _NoPasswordUser:
    """A user that names itself and exposes nothing a digest could cover."""

    __slots__ = ("_identifier",)

    def __init__(self, identifier: str) -> None:
        self._identifier = identifier

    def get_user_identifier(self) -> str:
        return self._identifier

    def get_roles(self) -> tuple[str, ...]:
        return ()


@final
class _VerifyingProvider(RecordingTokenProvider):
    """A token provider that is also its own verifier, as a store that can."""

    __slots__ = ("verifications",)

    def __init__(self, tokens: dict[str, PersistentToken] | None = None) -> None:
        super().__init__(tokens)
        self.verifications: list[tuple[PersistentToken, str]] = []

    async def verify_token(self, token: PersistentToken, token_value: str) -> bool:
        """Accept any value once — the window's policy — recording the check."""
        self.verifications.append((token, token_value))
        return True

    async def update_existing_token(
        self,
        token: PersistentToken,
        token_value: str,
        last_used: datetime,
    ) -> None:
        """Record the rotation the handler asked the verifier for."""
        self.updated.append((token.get_series(), token_value, last_used))


def _request(*, cookie: str | None = None) -> ServerRequestInterface:
    """Build a request whose state bag is parked, carrying ``cookie`` when given."""
    message = make_message()
    if cookie is not None:
        message = message.with_cookie_params({"REMEMBERME": cookie})
    bag: dict[str, object] = {}
    return message.with_attribute(SecurityRequestAttributes.STATE_BAG, bag)


def _staged_of(request: ServerRequestInterface) -> RememberMeCookie | None:
    """Return the cookie a handler staged on the request's state, if one is."""
    bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
    assert isinstance(bag, dict)
    staged = security_state_of(cast("dict[str, object]", bag)).attributes.get(
        SecurityRequestAttributes.REMEMBER_ME_COOKIE,
    )
    return staged if isinstance(staged, RememberMeCookie) else None


def _details_of(cookie: RememberMeCookie | None) -> RememberMeDetails:
    """Read a staged cookie's value back into the details it was written from."""
    assert cookie is not None
    assert cookie.value is not None
    return RememberMeDetails.from_raw_cookie(cookie.value)


def _handler(
    clock: MockClock,
    user: UserInterface,
) -> tuple[PersistentRememberMeHandler, RecordingTokenProvider, RecordingUserProvider]:
    """Build the handler over a frozen clock, its user registered with the provider."""
    provider = RecordingTokenProvider()
    user_provider = RecordingUserProvider({user.get_user_identifier(): user})
    handler = PersistentRememberMeHandler(provider, user_provider, clock=clock)
    return handler, provider, user_provider


def test_the_handler_satisfies_the_interface() -> None:
    handler, _provider, _users = _handler(MockClock(_FROZEN), InMemoryUser("ada"))

    assert isinstance(handler, RememberMeHandlerInterface)


async def test_create_stores_a_series_and_stages_its_first_cookie() -> None:
    clock = MockClock(_FROZEN)
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider, _users = _handler(clock, user)
    request = _request()

    await handler.create_remember_me_cookie(request, user)

    assert len(provider.created) == 1
    token = provider.created[0]
    assert token.get_user_identifier() == "ada"
    # 33 random bytes: 44 characters of the cookie's alphabet, neither part
    # derivable from the other.
    assert len(token.get_series()) == 44
    assert len(token.get_token_value().partition(".")[0]) == 44
    cookie = _staged_of(request)
    assert cookie is not None
    details = _details_of(cookie)
    assert details.get_user_identifier() == "ada"
    assert details.get_expires() == int(clock.now().timestamp()) + _ONE_YEAR
    assert details.get_value() == f"{token.get_series()}:{token.get_token_value()}"


async def test_create_binds_the_passwords_digest_to_the_value() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider, _users = _handler(MockClock(_FROZEN), user)
    request = _request()

    await handler.create_remember_me_cookie(request, user)

    token = provider.created[0]
    random_part, separator, digest = token.get_token_value().partition(".")
    assert separator == "."
    assert len(random_part) == 44
    # 24 bytes of digest: 32 characters, the store column's documented width.
    assert len(digest) == 32


async def test_create_leaves_a_user_without_the_property_unbound() -> None:
    user = _NoPasswordUser("ada")
    handler, provider, _users = _handler(MockClock(_FROZEN), user)
    request = _request()

    await handler.create_remember_me_cookie(request, user)

    assert "." not in provider.created[0].get_token_value()


async def test_consume_loads_the_user_and_rotates_the_stored_value() -> None:
    clock = MockClock(_FROZEN)
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider, _users = _handler(clock, user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    clock.sleep(_WINDOW + 1)

    presented = _request()
    loaded = await handler.consume_remember_me_cookie(presented, details)

    assert loaded.get_user_identifier() == "ada"
    assert len(provider.updated) == 1
    series, new_value, _last_used = provider.updated[0]
    assert series == details.get_value().partition(":")[0]
    assert new_value != details.get_value().partition(":")[2]
    assert provider.series[series].get_token_value() == new_value
    cookie = _staged_of(presented)
    assert cookie is not None
    assert _details_of(cookie).get_value() == f"{series}:{new_value}"


async def test_consume_within_the_rotation_window_changes_nothing() -> None:
    clock = MockClock(_FROZEN)
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider, _users = _handler(clock, user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    clock.sleep(_WINDOW - 1)

    presented = _request()
    loaded = await handler.consume_remember_me_cookie(presented, details)

    assert loaded.get_user_identifier() == "ada"
    assert provider.updated == []
    assert _staged_of(presented) is None


async def test_consume_refuses_a_value_the_store_no_longer_holds() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider, _users = _handler(MockClock(_FROZEN), user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    series = details.get_value().partition(":")[0]

    with pytest.raises(CookieTheftError, match="already used"):
        _ = await handler.consume_remember_me_cookie(
            _request(),
            details.with_value(f"{series}:spent"),
        )


async def test_consume_consults_the_verifier_over_the_plain_equality() -> None:
    clock = MockClock(_FROZEN)
    user = InMemoryUser("ada", password=_HASHED)
    provider = RecordingTokenProvider()
    verifier = RecordingTokenVerifier(accepts=True)
    handler = PersistentRememberMeHandler(
        provider,
        RecordingUserProvider({"ada": user}),
        clock=clock,
        token_verifier=verifier,
    )
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    series = details.get_value().partition(":")[0]
    clock.sleep(_WINDOW + 1)

    loaded = await handler.consume_remember_me_cookie(
        _request(),
        details.with_value(f"{series}:a-value-the-store-no-longer-holds"),
    )

    assert loaded.get_user_identifier() == "ada"
    assert len(verifier.recorded) == 1
    assert verifier.recorded[0][1] == "a-value-the-store-no-longer-holds"
    assert len(verifier.updates) == 1


async def test_a_provider_that_verifies_is_its_own_verifier() -> None:
    clock = MockClock(_FROZEN)
    user = InMemoryUser("ada", password=_HASHED)
    provider = _VerifyingProvider()
    handler = PersistentRememberMeHandler(
        provider,
        RecordingUserProvider({"ada": user}),
        clock=clock,
    )
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    series = details.get_value().partition(":")[0]
    clock.sleep(_WINDOW + 1)

    loaded = await handler.consume_remember_me_cookie(
        _request(),
        details.with_value(f"{series}:a-value-the-store-no-longer-holds"),
    )

    assert loaded.get_user_identifier() == "ada"
    assert len(provider.verifications) == 1


async def test_consume_refuses_a_cookie_naming_another_user() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider, _users = _handler(MockClock(_FROZEN), user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    other = RememberMeDetails("grace", details.get_expires(), details.get_value())

    with pytest.raises(AuthenticationError, match="hash is invalid"):
        _ = await handler.consume_remember_me_cookie(_request(), other)


async def test_consume_refuses_a_series_not_used_within_its_lifetime() -> None:
    clock = MockClock(_FROZEN)
    user = InMemoryUser("ada", password=_HASHED)
    handler, _provider, _users = _handler(clock, user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    clock.sleep(_ONE_YEAR + 10)

    with pytest.raises(AuthenticationError, match="expired"):
        _ = await handler.consume_remember_me_cookie(_request(), details)


async def test_consume_refuses_a_value_that_is_not_a_series_and_a_value() -> None:
    handler, _provider, _users = _handler(MockClock(_FROZEN), InMemoryUser("ada"))

    with pytest.raises(AuthenticationError, match="incorrectly formatted"):
        _ = await handler.consume_remember_me_cookie(
            _request(),
            RememberMeDetails("ada", 1, "nonsense"),
        )


async def test_consume_refuses_a_cookie_whose_user_changed_their_password() -> None:
    clock = MockClock(_FROZEN)
    user = InMemoryUser("ada", password=_HASHED)
    handler, _tokens, user_provider = _handler(clock, user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    details = _details_of(_staged_of(created))
    user_provider.users["ada"] = InMemoryUser("ada", password=_REHASHED)
    clock.sleep(_WINDOW + 1)

    with pytest.raises(AuthenticationError, match="hash is invalid"):
        _ = await handler.consume_remember_me_cookie(_request(), details)


async def test_clear_drops_the_series_the_requests_own_cookie_names() -> None:
    user = InMemoryUser("ada", password=_HASHED)
    handler, provider, _users = _handler(MockClock(_FROZEN), user)
    created = _request()
    await handler.create_remember_me_cookie(created, user)
    cookie = _staged_of(created)
    assert cookie is not None
    assert cookie.value is not None
    series = RememberMeDetails.from_raw_cookie(cookie.value).get_value().partition(":")[0]

    leaving = _request(cookie=cookie.value)
    await handler.clear_remember_me_cookie(leaving)

    assert provider.deleted == [series]
    cleared = _staged_of(leaving)
    assert cleared is not None
    assert cleared.value is None


async def test_clear_without_a_cookie_drops_no_series() -> None:
    handler, provider, _users = _handler(MockClock(_FROZEN), InMemoryUser("ada"))
    request = _request()

    await handler.clear_remember_me_cookie(request)

    assert provider.deleted == []
    cleared = _staged_of(request)
    assert cleared is not None
    assert cleared.value is None


async def test_clear_ignores_a_cookie_too_malformed_to_name_a_series() -> None:
    handler, provider, _users = _handler(MockClock(_FROZEN), InMemoryUser("ada"))
    request = _request(cookie="nonsense")

    await handler.clear_remember_me_cookie(request)

    assert provider.deleted == []
