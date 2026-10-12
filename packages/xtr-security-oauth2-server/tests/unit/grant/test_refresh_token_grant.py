"""A refresh token buys a new pair, and is spent doing it."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, final

import pytest

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.encryption import seal
from tests.support.entities import RefreshToken, make_client
from tests.support.grants import Storage, wire
from tests.support.messages import server_request
from tests.support.repositories import InMemoryScopeRepository
from tests.support.response_types import RecordingResponseType
from tests.support.signing import FROZEN_NOW, make_clock
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.grant.refresh_token_grant import RefreshTokenGrant
from xtr_security_oauth2_server.request_event import RequestEvent

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )
    from xtr_security_oauth2_server.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )

_AN_HOUR = timedelta(hours=1)


@final
class _LostTheRace:
    """A repository where the token reads valid and is revoked by somebody else."""

    async def get_new_refresh_token(self) -> RefreshTokenEntityInterface | None:
        return RefreshToken()

    async def persist_new_refresh_token(
        self,
        refresh_token_entity: RefreshTokenEntityInterface,
    ) -> None:
        del refresh_token_entity

    async def revoke_refresh_token(self, token_id: str) -> bool:
        del token_id

        return False

    async def is_refresh_token_revoked(self, token_id: str) -> bool:
        del token_id

        return False


def _sealed(**overrides: object) -> str:
    payload: dict[str, object] = {
        "client_id": "client-1",
        "refresh_token_id": "refresh-1",
        "access_token_id": "access-1",
        "scopes": ["read", "write"],
        "user_id": "user-1",
        "expire_time": int((FROZEN_NOW + timedelta(days=30)).timestamp()),
    }
    payload.update(overrides)

    return seal(payload)


def _token_request(**body: str) -> ServerRequestInterface:
    return server_request(
        "POST",
        "/token",
        parsed_body={"client_id": "client-1", "client_secret": "secret", **body},
    )


def _grant(
    storage: Storage,
    repository: RefreshTokenRepositoryInterface | None = None,
) -> tuple[RefreshTokenGrant, RecordingEventDispatcher]:
    storage.clients.add(make_client("client-1"), "secret")
    dispatcher = RecordingEventDispatcher()
    held = repository if repository is not None else storage.refresh_tokens
    grant = RefreshTokenGrant(dispatcher, make_clock(), held)
    wire(grant, storage)

    return grant, dispatcher


def _known_scopes() -> Storage:
    return Storage(scopes=InMemoryScopeRepository("read", "write"))


def test_it_is_asked_for_by_name() -> None:
    grant, _ = _grant(Storage())

    assert grant.get_identifier() == "refresh_token"


@pytest.mark.anyio
async def test_a_valid_refresh_token_buys_a_new_pair() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=_sealed()),
        response_type,
        _AN_HOUR,
    )

    assert response_type.access_token is not None
    assert response_type.refresh_token is not None


@pytest.mark.anyio
async def test_the_new_token_is_issued_for_the_resource_owner_the_old_one_named() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=_sealed()),
        response_type,
        _AN_HOUR,
    )

    assert response_type.access_token is not None
    assert response_type.access_token.get_user_identifier() == "user-1"
    assert storage.scopes.finalized[0].user_identifier == "user-1"


@pytest.mark.anyio
async def test_a_resource_owner_recorded_as_a_number_is_read_as_a_name() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=_sealed(user_id=42)),
        response_type,
        _AN_HOUR,
    )

    assert response_type.access_token is not None
    assert response_type.access_token.get_user_identifier() == "42"


@pytest.mark.anyio
async def test_the_access_token_the_old_refresh_token_came_with_is_revoked() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=_sealed()),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert await storage.access_tokens.is_access_token_revoked("access-1") is True


@pytest.mark.anyio
async def test_the_refresh_token_that_was_spent_is_revoked() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=_sealed()),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert await storage.refresh_tokens.is_refresh_token_revoked("refresh-1") is True


@pytest.mark.anyio
async def test_a_deployment_that_keeps_its_refresh_tokens_does_not_revoke_the_old_one() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)
    grant.revoke_refresh_tokens(will_revoke=False)

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=_sealed()),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert await storage.refresh_tokens.is_refresh_token_revoked("refresh-1") is False


@pytest.mark.anyio
async def test_losing_the_race_to_revoke_the_token_hands_out_nothing() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage, _LostTheRace())
    response_type = RecordingResponseType()

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(refresh_token=_sealed()),
            response_type,
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_grant"
    assert response_type.access_token is None


@pytest.mark.anyio
async def test_both_new_tokens_are_announced() -> None:
    storage = _known_scopes()
    grant, dispatcher = _grant(storage)

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=_sealed()),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert dispatcher.names() == (
        RequestEvent.ACCESS_TOKEN_ISSUED,
        RequestEvent.REFRESH_TOKEN_ISSUED,
    )


@pytest.mark.anyio
async def test_a_request_carrying_no_refresh_token_is_refused() -> None:
    grant, _ = _grant(_known_scopes())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_request"
    assert "refresh_token" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_refresh_token_this_server_did_not_seal_is_refused() -> None:
    grant, _ = _grant(_known_scopes())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(refresh_token="not-a-sealed-payload"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_grant"
    assert "decrypt" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_refresh_token_of_another_client_is_refused_and_announced() -> None:
    grant, dispatcher = _grant(_known_scopes())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(refresh_token=_sealed(client_id="client-2")),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_grant"
    assert dispatcher.names() == (RequestEvent.REFRESH_TOKEN_CLIENT_FAILED,)


@pytest.mark.anyio
async def test_an_expired_refresh_token_is_refused() -> None:
    grant, _ = _grant(_known_scopes())
    expired = int((FROZEN_NOW - timedelta(seconds=1)).timestamp())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(refresh_token=_sealed(expire_time=expired)),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "expired" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_refresh_token_whose_expiry_is_not_an_instant_is_refused() -> None:
    grant, _ = _grant(_known_scopes())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(refresh_token=_sealed(expire_time="whenever")),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "expired" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_refresh_token_carrying_no_scopes_asks_for_nothing() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)
    payload = {
        "client_id": "client-1",
        "refresh_token_id": "refresh-1",
        "access_token_id": "access-1",
        "user_id": "user-1",
        "expire_time": int((FROZEN_NOW + timedelta(days=30)).timestamp()),
    }

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=seal(payload)),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert tuple(storage.scopes.finalized[0].scopes) == ()


@pytest.mark.anyio
async def test_a_refresh_token_naming_no_resource_owner_refreshes_for_nobody() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=_sealed(user_id=None)),
        response_type,
        _AN_HOUR,
    )

    assert response_type.access_token is not None
    assert response_type.access_token.get_user_identifier() is None
    assert storage.scopes.finalized[0].user_identifier is None


@pytest.mark.anyio
async def test_a_refresh_token_already_revoked_is_refused() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)
    storage.refresh_tokens.revoked.add("refresh-1")

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(refresh_token=_sealed()),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "revoked" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_payload_naming_no_token_is_refused() -> None:
    grant, _ = _grant(_known_scopes())
    sealed = seal({"client_id": "client-1", "expire_time": 99999999999})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(refresh_token=sealed),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_grant"


@pytest.mark.anyio
async def test_a_request_naming_no_scope_keeps_the_ones_the_old_token_had() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=_sealed()),
        RecordingResponseType(),
        _AN_HOUR,
    )

    granted = [scope.get_identifier() for scope in storage.scopes.finalized[0].scopes]
    assert granted == ["read", "write"]


@pytest.mark.anyio
async def test_a_request_may_ask_for_fewer_scopes_than_the_old_token_had() -> None:
    storage = _known_scopes()
    grant, _ = _grant(storage)

    _ = await grant.respond_to_access_token_request(
        _token_request(refresh_token=_sealed(), scope="read"),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert [scope.get_identifier() for scope in storage.scopes.finalized[0].scopes] == ["read"]


@pytest.mark.anyio
async def test_a_request_may_not_ask_for_a_scope_the_old_token_did_not_have() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read", "write", "delete"))
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(refresh_token=_sealed(), scope="read delete"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_scope"
    assert "delete" in str(refusal.value.get_hint())
