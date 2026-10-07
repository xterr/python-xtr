"""The authenticator proves a caller by a token, and challenges without one."""

from __future__ import annotations

from typing import final

import pytest
from xtr_clock import MockClock
from xtr_security_core.user.chain_user_provider import ChainUserProvider
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import AbstractAuthenticator
from xtr_security_http.entry_point.authentication_entry_point_interface import (
    AuthenticationEntryPointInterface,
)

from tests.support.fakes import (
    AttributesRecordingProvider,
    PlainUserProvider,
    RecordingDispatcher,
)
from tests.support.keys import RSA_PRIVATE_PEM
from tests.support.requests import make_request
from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder
from xtr_security_jwt.event.jwt_authenticated_event import JwtAuthenticatedEvent
from xtr_security_jwt.event.jwt_expired_event import JwtExpiredEvent
from xtr_security_jwt.event.jwt_invalid_event import JwtInvalidEvent
from xtr_security_jwt.event.jwt_not_found_event import JwtNotFoundEvent
from xtr_security_jwt.exception.expired_token_error import ExpiredTokenError
from xtr_security_jwt.exception.invalid_payload_error import InvalidPayloadError
from xtr_security_jwt.exception.invalid_token_error import InvalidTokenError
from xtr_security_jwt.security.authenticator.jwt_authenticator import (
    JwtAuthenticator,
    _as_mapping,
)
from xtr_security_jwt.security.authenticator.token.jwt_post_authentication_token import (
    JwtPostAuthenticationToken,
)
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.jwt_manager import JwtManager
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader
from xtr_security_jwt.token_extractor.authorization_header_token_extractor import (
    AuthorizationHeaderTokenExtractor,
)

pytestmark = pytest.mark.anyio


def _manager(clock: MockClock, *, ttl: int = 3600, claim: str = "username") -> JwtManager:
    provider = JoserfcJwsProvider(RawKeyLoader(RSA_PRIVATE_PEM, None), "RS256", ttl, 0, clock)
    return JwtManager(
        DefaultJwtEncoder(provider),
        RecordingDispatcher(),
        claim,
        issuer="https://jwt.test",
    )


async def _token(clock: MockClock, identifier: str = "ada", *, ttl: int = 3600) -> str:
    return await _manager(clock, ttl=ttl).create(InMemoryUser(identifier, roles=["ROLE_USER"]))


def _authenticator(
    clock: MockClock,
    provider: UserProviderInterface,
    dispatcher: RecordingDispatcher | None = None,
    *,
    claim: str = "username",
) -> tuple[JwtAuthenticator, RecordingDispatcher]:
    the_dispatcher = dispatcher if dispatcher is not None else RecordingDispatcher()
    authenticator = JwtAuthenticator(
        _manager(clock, claim=claim),
        the_dispatcher,
        AuthorizationHeaderTokenExtractor(),
        provider,
        "api",
    )
    return authenticator, the_dispatcher


def test_it_is_an_abstract_authenticator_and_an_entry_point() -> None:
    assert AbstractAuthenticator in JwtAuthenticator.__mro__
    assert AuthenticationEntryPointInterface in JwtAuthenticator.__mro__


async def test_supports_true_with_a_token_and_false_without() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, _ = _authenticator(clock, PlainUserProvider(InMemoryUser("ada")))
    with_token = make_request(headers={"Authorization": "Bearer x"})

    assert authenticator.supports(with_token) is True
    assert authenticator.supports(make_request()) is False


async def test_authenticate_builds_a_passport_and_loads_the_user() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    provider = AttributesRecordingProvider(InMemoryUser("ada", roles=["ROLE_USER"]))
    authenticator, _ = _authenticator(clock, provider)
    token = await _token(clock)
    request = make_request(headers={"Authorization": f"Bearer {token}"})

    passport = await authenticator.authenticate(request)
    user = await passport.get_user()

    assert user.get_user_identifier() == "ada"
    assert provider.attributes and provider.attributes[0] is not None


async def test_an_attributes_provider_receives_the_payload() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    provider = AttributesRecordingProvider(InMemoryUser("ada"))
    authenticator, _ = _authenticator(clock, provider)
    token = await _token(clock)
    passport = await authenticator.authenticate(
        make_request(headers={"Authorization": f"Bearer {token}"}),
    )
    _ = await passport.get_user()

    payload = provider.attributes[0]
    assert payload is not None
    assert payload["username"] == "ada"


async def test_a_plain_provider_is_asked_by_identifier() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    provider = PlainUserProvider(InMemoryUser("ada"))
    authenticator, _ = _authenticator(clock, provider)
    token = await _token(clock)
    passport = await authenticator.authenticate(
        make_request(headers={"Authorization": f"Bearer {token}"}),
    )
    _ = await passport.get_user()

    assert provider.calls == ["ada"]


async def test_a_chain_provider_tries_each_member() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    plain = PlainUserProvider(InMemoryUser("ada"))
    chain = ChainUserProvider([plain])
    authenticator, _ = _authenticator(clock, chain)
    token = await _token(clock)
    passport = await authenticator.authenticate(
        make_request(headers={"Authorization": f"Bearer {token}"}),
    )
    user = await passport.get_user()

    assert user.get_user_identifier() == "ada"


async def test_an_expired_token_raises_expired() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, _ = _authenticator(clock, PlainUserProvider(InMemoryUser("ada")))
    token = await _token(clock, ttl=50)
    clock.sleep(100)

    with pytest.raises(ExpiredTokenError):
        _ = await authenticator.authenticate(
            make_request(headers={"Authorization": f"Bearer {token}"}),
        )


async def test_a_bad_token_raises_invalid() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, _ = _authenticator(clock, PlainUserProvider(InMemoryUser("ada")))

    with pytest.raises(InvalidTokenError):
        _ = await authenticator.authenticate(
            make_request(headers={"Authorization": "Bearer not.a.token"}),
        )


async def test_a_missing_id_claim_raises_invalid_payload() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, _ = _authenticator(
        clock,
        PlainUserProvider(InMemoryUser("ada")),
        claim="email",
    )
    # A token whose id claim is "username", read back expecting "email".
    token = await _manager(clock, claim="username").create(InMemoryUser("ada"))

    with pytest.raises(InvalidPayloadError):
        _ = await authenticator.authenticate(
            make_request(headers={"Authorization": f"Bearer {token}"}),
        )


async def test_create_token_builds_a_jwt_token_and_keeps_the_raw_token() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, _ = _authenticator(clock, PlainUserProvider(InMemoryUser("ada")))
    token = await _token(clock)
    passport = await authenticator.authenticate(
        make_request(headers={"Authorization": f"Bearer {token}"}),
    )
    _ = await passport.get_user()

    settled = await authenticator.create_token(passport, "api")

    assert isinstance(settled, JwtPostAuthenticationToken)
    assert settled.get_credentials() == token
    assert settled.get_firewall_name() == "api"


async def test_create_token_dispatches_jwt_authenticated() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, dispatcher = _authenticator(clock, PlainUserProvider(InMemoryUser("ada")))
    token = await _token(clock)
    passport = await authenticator.authenticate(
        make_request(headers={"Authorization": f"Bearer {token}"}),
    )
    _ = await passport.get_user()
    dispatcher.events.clear()

    _ = await authenticator.create_token(passport, "api")

    assert dispatcher.types() == [JwtAuthenticatedEvent]


async def test_on_success_answers_nothing() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, _ = _authenticator(clock, PlainUserProvider(InMemoryUser("ada")))
    token = await _token(clock)
    passport = await authenticator.authenticate(
        make_request(headers={"Authorization": f"Bearer {token}"}),
    )
    _ = await passport.get_user()
    settled = await authenticator.create_token(passport, "api")

    assert await authenticator.on_authentication_success(make_request(), settled, "api") is None


async def test_on_failure_of_an_expired_token_answers_401_and_dispatches_expired() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, dispatcher = _authenticator(clock, PlainUserProvider(InMemoryUser("ada")))

    response = await authenticator.on_authentication_failure(make_request(), ExpiredTokenError())

    assert response is not None
    assert response.status_code == 401
    assert JwtExpiredEvent in dispatcher.types()


async def test_on_failure_of_an_invalid_token_dispatches_invalid() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, dispatcher = _authenticator(clock, PlainUserProvider(InMemoryUser("ada")))

    response = await authenticator.on_authentication_failure(make_request(), InvalidTokenError())

    assert response is not None
    assert JwtInvalidEvent in dispatcher.types()


async def test_start_answers_401_not_found_and_dispatches_not_found() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, dispatcher = _authenticator(clock, PlainUserProvider(InMemoryUser("ada")))

    response = await authenticator.start(make_request())

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert JwtNotFoundEvent in dispatcher.types()


async def test_start_keeps_the_given_error_as_the_cause_of_the_not_found() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    authenticator, dispatcher = _authenticator(clock, PlainUserProvider(InMemoryUser("ada")))
    drew_the_challenge = InvalidTokenError("the firewall fell through")

    _ = await authenticator.start(make_request(), drew_the_challenge)

    event = dispatcher.events[-1]
    assert isinstance(event, JwtNotFoundEvent)
    assert event.get_exception().__cause__ is drew_the_challenge


def test_as_mapping_raises_invalid_token_naming_the_payload_for_a_non_mapping() -> None:
    with pytest.raises(InvalidTokenError, match="payload is not a mapping"):
        _ = _as_mapping("not-a-mapping")


def test_as_mapping_returns_a_mapping_unchanged() -> None:
    payload = {"sub": "ada"}

    assert _as_mapping(payload) == payload


async def test_the_token_is_extracted_once_per_request() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    token = await _token(clock)
    extractor = _CountingExtractor(token)
    authenticator = JwtAuthenticator(
        _manager(clock),
        RecordingDispatcher(),
        extractor,
        PlainUserProvider(InMemoryUser("ada", roles=["ROLE_USER"])),
        "api",
    )
    request = make_request(headers={"Authorization": f"Bearer {token}"})

    assert authenticator.supports(request) is True
    passport = await authenticator.authenticate(request)

    assert (await passport.get_user()).get_user_identifier() == "ada"
    assert extractor.calls == 1


async def test_two_firewalls_sharing_a_request_each_extract_their_own_token() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    token = await _token(clock)
    first = _CountingExtractor(token)
    second = _CountingExtractor(token)
    provider = PlainUserProvider(InMemoryUser("ada", roles=["ROLE_USER"]))
    api = JwtAuthenticator(_manager(clock), RecordingDispatcher(), first, provider, "api")
    admin = JwtAuthenticator(_manager(clock), RecordingDispatcher(), second, provider, "admin")
    request = make_request(headers={"Authorization": f"Bearer {token}"})

    assert (api.supports(request), admin.supports(request)) == (True, True)
    assert api.supports(request) is True

    assert (first.calls, second.calls) == (1, 1)


@final
class _CountingExtractor:
    """A token extractor that returns a fixed token and counts its calls."""

    def __init__(self, token: str) -> None:
        self._token = token
        self.calls = 0

    def extract(self, request: object) -> str | None:
        del request
        self.calls += 1
        return self._token
