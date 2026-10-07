"""The token manager assembles, announces and signs a token, and reads one back."""

from __future__ import annotations

import pytest
from xtr_clock import MockClock
from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.fakes import (
    AttributedUser,
    PlainUserProvider,
    RecordingDispatcher,
    RejectingDispatcher,
)
from tests.support.keys import RSA_PRIVATE_PEM
from tests.support.requests import make_request
from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder
from xtr_security_jwt.event.jwt_created_event import JwtCreatedEvent
from xtr_security_jwt.event.jwt_decoded_event import JwtDecodedEvent
from xtr_security_jwt.event.jwt_encoded_event import JwtEncodedEvent
from xtr_security_jwt.exception.jwt_decode_failure_error import JwtDecodeFailureError
from xtr_security_jwt.security.authenticator.jwt_authenticator import JwtAuthenticator
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.jwt_manager import JwtManager
from xtr_security_jwt.services.jwt_token_manager_interface import JwtTokenManagerInterface
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader
from xtr_security_jwt.services.payload_enrichment.random_jti_enrichment import RandomJtiEnrichment
from xtr_security_jwt.token_extractor.authorization_header_token_extractor import (
    AuthorizationHeaderTokenExtractor,
)

pytestmark = pytest.mark.anyio


def _encoder(clock: MockClock, *, ttl: int = 3600) -> DefaultJwtEncoder:
    provider = JoserfcJwsProvider(RawKeyLoader(RSA_PRIVATE_PEM, None), "RS256", ttl, 0, clock)
    return DefaultJwtEncoder(provider)


def _manager(
    clock: MockClock | None = None,
    *,
    user_id_claim: str = "username",
    enrichment: RandomJtiEnrichment | None = None,
    issuer: str = "https://jwt.test",
    audience: tuple[str, ...] = (),
) -> tuple[JwtManager, RecordingDispatcher]:
    the_clock = clock if clock is not None else MockClock("2024-01-01 00:00:00")
    dispatcher = RecordingDispatcher()
    manager = JwtManager(
        _encoder(the_clock),
        dispatcher,
        user_id_claim,
        enrichment,
        issuer=issuer,
        audience=audience,
    )
    return manager, dispatcher


def test_it_implements_the_manager_interface() -> None:
    manager, _ = _manager()
    assert isinstance(manager, JwtTokenManagerInterface)


async def test_create_carries_roles_and_the_user_id_claim() -> None:
    manager, _ = _manager()
    token = await manager.create(InMemoryUser("ada", roles=["ROLE_USER"]))
    payload = await manager.parse(token)

    assert payload["username"] == "ada"
    assert payload["roles"] == ["ROLE_USER"]


async def test_create_dispatches_created_and_encoded() -> None:
    manager, dispatcher = _manager()
    _ = await manager.create(InMemoryUser("ada"))

    assert dispatcher.types() == [JwtCreatedEvent, JwtEncodedEvent]


async def test_parse_dispatches_decoded() -> None:
    manager, dispatcher = _manager()
    token = await manager.create(InMemoryUser("ada"))
    dispatcher.events.clear()
    _ = await manager.parse(token)

    assert dispatcher.types() == [JwtDecodedEvent]


async def test_the_id_claim_reads_a_user_attribute_when_present() -> None:
    manager, _ = _manager(user_id_claim="email")
    token = await manager.create(AttributedUser("ada", "ada@example.test"))
    payload = await manager.parse(token)

    assert payload["email"] == "ada@example.test"


async def test_the_id_claim_falls_back_to_the_identifier() -> None:
    manager, _ = _manager(user_id_claim="email")
    token = await manager.create(InMemoryUser("ada"))
    payload = await manager.parse(token)

    assert payload["email"] == "ada"


async def test_create_from_payload_merges_the_caller_claims() -> None:
    manager, _ = _manager()
    token = await manager.create_from_payload(InMemoryUser("ada"), {"tenant": "acme"})
    payload = await manager.parse(token)

    assert payload["tenant"] == "acme"
    assert payload["username"] == "ada"


async def test_enrichment_stamps_a_claim() -> None:
    manager, _ = _manager(enrichment=RandomJtiEnrichment())
    token = await manager.create(InMemoryUser("ada"))
    payload = await manager.parse(token)

    assert "jti" in payload


async def test_decode_reads_the_credentials_of_a_settled_security_token() -> None:
    # The token is the one a firewall really settles on, built by the
    # authenticator, so decode is proved against the token it will be handed.
    user = InMemoryUser("ada", roles=["ROLE_USER"])
    manager, _ = _manager()
    raw = await manager.create(user)
    authenticator = JwtAuthenticator(
        manager,
        RecordingDispatcher(),
        AuthorizationHeaderTokenExtractor(),
        PlainUserProvider(user),
        "api",
    )
    passport = await authenticator.authenticate(
        make_request(headers={"Authorization": f"Bearer {raw}"}),
    )
    _ = await passport.get_user()
    settled = await authenticator.create_token(passport, "api")

    decoded = await manager.decode(settled)

    assert isinstance(decoded, dict)
    assert decoded["username"] == "ada"


async def test_decode_returns_false_for_a_token_carrying_no_credentials() -> None:
    manager, _ = _manager()

    assert await manager.decode(_PlainToken()) is False


async def test_parse_that_a_listener_rejects_fails() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    manager = JwtManager(
        _encoder(clock),
        RejectingDispatcher(JwtDecodedEvent),
        "username",
        issuer="https://jwt.test",
    )
    token = await manager.create(InMemoryUser("ada"))

    with pytest.raises(JwtDecodeFailureError):
        _ = await manager.parse(token)


def test_get_user_id_claim_reports_the_configured_claim() -> None:
    manager, _ = _manager(user_id_claim="sub")
    assert manager.get_user_id_claim() == "sub"


async def test_create_stamps_the_issuer() -> None:
    manager, _ = _manager(issuer="issuer-a")
    payload = await manager.parse(await manager.create(InMemoryUser("ada")))

    assert payload["iss"] == "issuer-a"


async def test_a_token_minted_for_another_issuer_is_refused() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    minted, _ = _manager(clock, issuer="issuer-a")
    verifier, _ = _manager(clock, issuer="issuer-b")
    token = await minted.create(InMemoryUser("ada"))

    with pytest.raises(JwtDecodeFailureError):
        _ = await verifier.parse(token)


async def test_create_stamps_the_audience_when_set() -> None:
    manager, _ = _manager(audience=("aud-a",))
    payload = await manager.parse(await manager.create(InMemoryUser("ada")))

    assert payload["aud"] == ["aud-a"]


async def test_a_token_for_another_audience_is_refused() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    minted, _ = _manager(clock, audience=("aud-a",))
    verifier, _ = _manager(clock, audience=("aud-b",))
    token = await minted.create(InMemoryUser("ada"))

    with pytest.raises(JwtDecodeFailureError):
        _ = await verifier.parse(token)


async def test_a_token_naming_one_of_several_audiences_is_accepted() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    minted, _ = _manager(clock, audience=("aud-a", "aud-b"))
    verifier, _ = _manager(clock, audience=("aud-b",))
    token = await minted.create(InMemoryUser("ada"))

    payload = await verifier.parse(token)

    assert payload["aud"] == ["aud-a", "aud-b"]


async def test_a_token_naming_an_audience_is_refused_when_none_is_configured() -> None:
    # RFC 7519 section 4.1.3: a reader that does not identify itself with the
    # audience the token names must refuse it, and a deployment configuring no
    # audience identifies itself with none.
    clock = MockClock("2024-01-01 00:00:00")
    minted, _ = _manager(clock, audience=("aud-a",))
    verifier, _ = _manager(clock)
    token = await minted.create(InMemoryUser("ada"))

    with pytest.raises(JwtDecodeFailureError, match="names an audience"):
        _ = await verifier.parse(token)


async def test_a_token_naming_no_audience_is_accepted_when_none_is_configured() -> None:
    manager, _ = _manager()

    payload = await manager.parse(await manager.create(InMemoryUser("ada")))

    assert "aud" not in payload


async def test_create_from_payload_does_not_let_a_caller_widen_roles() -> None:
    manager, _ = _manager()
    token = await manager.create_from_payload(
        InMemoryUser("ada", roles=["ROLE_USER"]),
        {"roles": ["ROLE_ADMIN"]},
    )
    payload = await manager.parse(token)

    assert payload["roles"] == ["ROLE_USER"]


def test_an_audience_given_as_one_string_is_refused() -> None:
    # A bare string is a sequence of its own letters, so an audience of "api"
    # would be read as ("a", "p", "i") and a token claiming "a" would pass.
    clock = MockClock("2024-01-01 00:00:00")

    with pytest.raises(InvalidArgumentError, match=r"audience=\('api',\)"):
        _ = JwtManager(
            _encoder(clock),
            RecordingDispatcher(),
            "username",
            issuer="https://jwt.test",
            audience="api",
        )


class _PlainToken(AbstractToken):
    """A security token of another kind: it keeps no compact token at all."""

    def __init__(self) -> None:
        super().__init__(user=None, roles=())
