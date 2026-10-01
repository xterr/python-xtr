"""The token manager assembles, announces and signs a token, and reads one back."""

from __future__ import annotations

import pytest
from xtr_clock import MockClock
from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.fakes import AttributedUser, RecordingDispatcher, RejectingDispatcher
from tests.support.keys import RSA_PRIVATE_PEM
from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder
from xtr_security_jwt.events import Events
from xtr_security_jwt.exception.jwt_decode_failure_error import JwtDecodeFailureError
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.jwt_manager import JwtManager
from xtr_security_jwt.services.jwt_token_manager_interface import JwtTokenManagerInterface
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader
from xtr_security_jwt.services.payload_enrichment.random_jti_enrichment import RandomJtiEnrichment

pytestmark = pytest.mark.anyio


def _encoder(clock: MockClock, *, ttl: int = 3600) -> DefaultJwtEncoder:
    provider = JoserfcJwsProvider(RawKeyLoader(RSA_PRIVATE_PEM, None), "RS256", ttl, 0, clock)
    return DefaultJwtEncoder(provider)


def _manager(
    clock: MockClock | None = None,
    *,
    user_id_claim: str = "username",
    enrichment: RandomJtiEnrichment | None = None,
) -> tuple[JwtManager, RecordingDispatcher]:
    the_clock = clock if clock is not None else MockClock("2024-01-01 00:00:00")
    dispatcher = RecordingDispatcher()
    manager = JwtManager(_encoder(the_clock), dispatcher, user_id_claim, enrichment)
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

    assert dispatcher.names() == [Events.JWT_CREATED, Events.JWT_ENCODED]


async def test_parse_dispatches_decoded() -> None:
    manager, dispatcher = _manager()
    token = await manager.create(InMemoryUser("ada"))
    dispatcher.events.clear()
    _ = await manager.parse(token)

    assert dispatcher.names() == [Events.JWT_DECODED]


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


async def test_decode_reads_a_stored_token_credentials() -> None:
    manager, _ = _manager()
    raw = await manager.create(InMemoryUser("ada"))
    token = _StoredToken(raw)

    decoded = await manager.decode(token)

    assert isinstance(decoded, dict)
    assert decoded["username"] == "ada"


async def test_decode_returns_false_without_credentials() -> None:
    manager, _ = _manager()

    assert await manager.decode(_StoredToken(None)) is False


async def test_parse_that_a_listener_rejects_fails() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    manager = JwtManager(_encoder(clock), RejectingDispatcher(Events.JWT_DECODED), "username")
    token = await manager.create(InMemoryUser("ada"))

    with pytest.raises(JwtDecodeFailureError):
        _ = await manager.parse(token)


def test_get_user_id_claim_reports_the_configured_claim() -> None:
    manager, _ = _manager(user_id_claim="sub")
    assert manager.get_user_id_claim() == "sub"


class _StoredToken(AbstractToken):
    def __init__(self, raw: str | None) -> None:
        super().__init__(user=None, roles=())
        if raw is not None:
            self.set_attribute("token", raw)
