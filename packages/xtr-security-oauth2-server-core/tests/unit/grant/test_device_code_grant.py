"""A device with no keyboard polls while its owner approves it elsewhere."""

from __future__ import annotations

import base64
from datetime import timedelta
from typing import TYPE_CHECKING, cast

import pytest
from xtr_http_message import Response

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entities import make_client
from tests.support.grants import Storage, wire
from tests.support.messages import document_of, server_request
from tests.support.repositories import InMemoryScopeRepository
from tests.support.response_types import RecordingResponseType
from tests.support.signing import make_clock
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.grant.device_code_grant import (
    USER_CODE_ALPHABET,
    DeviceCodeGrant,
)
from xtr_security_oauth2_server_core.request_event import RequestEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import MockClock
    from xtr_http_message_contracts import ServerRequestInterface

_AN_HOUR = timedelta(hours=1)
_TEN_MINUTES = timedelta(minutes=10)
_VERIFICATION_URI = "https://example.com/device"
_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


def _device_request(**body: str) -> ServerRequestInterface:
    return server_request("POST", "/device-code", parsed_body=body)


def _token_request(**body: str) -> ServerRequestInterface:
    return server_request(
        "POST",
        "/token",
        parsed_body={"client_id": "client-1", "client_secret": "secret", **body},
    )


def _grant(
    storage: Storage,
    clock: MockClock | None = None,
) -> tuple[DeviceCodeGrant, RecordingEventDispatcher, MockClock]:
    storage.clients.add(make_client("client-1"), "secret")
    reading = clock if clock is not None else make_clock()
    dispatcher = RecordingEventDispatcher()
    grant = DeviceCodeGrant(
        dispatcher,
        reading,
        storage.device_codes,
        storage.refresh_tokens,
        _TEN_MINUTES,
        _VERIFICATION_URI,
    )
    wire(grant, storage, reading)

    return grant, dispatcher, reading


async def _issued(grant: DeviceCodeGrant, **body: str) -> Mapping[str, object]:
    response_type = await grant.respond_to_device_authorization_request(
        _device_request(client_id="client-1", **body),
    )

    return cast(
        "Mapping[str, object]",
        await document_of(await response_type.generate_http_response(Response())),
    )


async def _approved_code(grant: DeviceCodeGrant, storage: Storage) -> str:
    issued = await _issued(grant)
    device_code = str(issued["device_code"])
    await grant.complete_device_authorization_request(device_code, "user-1", user_approved=True)
    assert storage.device_codes.codes[device_code].get_user_approved() is True

    return device_code


def test_it_is_asked_for_by_name() -> None:
    grant, _, _ = _grant(Storage())

    assert grant.get_identifier() == _GRANT_TYPE


def test_it_answers_a_device_authorization_request() -> None:
    grant, _, _ = _grant(Storage())

    assert grant.can_respond_to_device_authorization_request(_device_request()) is True


@pytest.mark.anyio
async def test_a_device_is_handed_a_code_to_poll_with_and_one_to_type_in() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)

    issued = await _issued(grant)

    assert len(str(issued["device_code"])) == 80
    assert len(str(issued["user_code"])) == 8
    assert set(str(issued["user_code"])) <= set(USER_CODE_ALPHABET)
    assert issued["verification_uri"] == _VERIFICATION_URI
    assert issued["expires_in"] == 600


@pytest.mark.anyio
async def test_the_code_it_issues_is_stored_against_the_client_and_the_scopes() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read"))
    grant, _, _ = _grant(storage)

    issued = await _issued(grant, scope="read")

    stored = storage.device_codes.codes[str(issued["device_code"])]
    assert stored.get_client().get_identifier() == "client-1"
    assert [scope.get_identifier() for scope in stored.get_scopes()] == ["read"]
    assert stored.get_interval() == 5


@pytest.mark.anyio
async def test_the_pre_filled_uri_and_the_interval_are_left_out_unless_asked_for() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)

    issued = await _issued(grant)

    assert "verification_uri_complete" not in issued
    assert "interval" not in issued


@pytest.mark.anyio
async def test_a_deployment_may_send_the_pre_filled_uri_and_the_interval() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    grant.set_include_verification_uri_complete(True)
    grant.set_interval_visibility(True)

    issued = await _issued(grant)

    assert str(issued["verification_uri_complete"]).startswith(f"{_VERIFICATION_URI}?user_code=")
    assert issued["interval"] == 5


def test_whether_the_interval_is_shown_is_readable() -> None:
    grant, _, _ = _grant(Storage())

    assert grant.get_interval_visibility() is False

    grant.set_interval_visibility(True)

    assert grant.get_interval_visibility() is True


@pytest.mark.anyio
async def test_a_deployment_may_change_where_resource_owners_are_sent() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    grant.set_verification_uri("https://example.com/activate")

    issued = await _issued(grant)

    assert issued["verification_uri"] == "https://example.com/activate"


@pytest.mark.anyio
async def test_a_device_authorization_request_naming_no_client_is_refused() -> None:
    grant, _, _ = _grant(Storage())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_device_authorization_request(_device_request())

    assert "client_id" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_device_may_name_its_client_in_the_authorization_header() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    encoded = base64.b64encode(b"client-1:secret").decode()
    request = server_request(
        "POST",
        "/device-code",
        headers={"Authorization": f"Basic {encoded}"},
    )

    response_type = await grant.respond_to_device_authorization_request(request)

    answer = await response_type.generate_http_response(Response())

    assert answer.get_status_code() == 200


@pytest.mark.anyio
async def test_a_device_asking_for_an_unknown_scope_is_refused() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read"))
    grant, _, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_device_authorization_request(
            _device_request(client_id="client-1", scope="delete"),
        )

    assert refusal.value.get_error_type() == "invalid_scope"


@pytest.mark.anyio
async def test_approving_a_code_records_the_owner_and_the_decision() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    issued = await _issued(grant)
    device_code = str(issued["device_code"])

    await grant.complete_device_authorization_request(device_code, "user-1", user_approved=True)

    stored = storage.device_codes.codes[device_code]
    assert stored.get_user_identifier() == "user-1"
    assert stored.get_user_approved() is True


@pytest.mark.anyio
async def test_approving_a_code_nobody_issued_is_refused() -> None:
    grant, _, _ = _grant(Storage())

    with pytest.raises(OAuthServerError) as refusal:
        await grant.complete_device_authorization_request("nobody", "user-1", user_approved=True)

    assert "does not exist" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_approving_a_code_on_behalf_of_nobody_is_refused() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    issued = await _issued(grant)

    with pytest.raises(OAuthServerError) as refusal:
        await grant.complete_device_authorization_request(
            str(issued["device_code"]),
            "",
            user_approved=True,
        )

    assert "User ID is required" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_first_poll_before_approval_is_told_to_keep_waiting() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    issued = await _issued(grant)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=str(issued["device_code"])),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "authorization_pending"


@pytest.mark.anyio
async def test_a_poll_is_recorded_even_though_it_is_refused() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    issued = await _issued(grant)
    device_code = str(issued["device_code"])

    with pytest.raises(OAuthServerError):
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=device_code),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert storage.device_codes.codes[device_code].get_last_polled_at() is not None


@pytest.mark.anyio
async def test_a_second_poll_too_soon_is_told_to_slow_down() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    issued = await _issued(grant)
    device_code = str(issued["device_code"])
    with pytest.raises(OAuthServerError):
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=device_code),
            RecordingResponseType(),
            _AN_HOUR,
        )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=device_code),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "slow_down"


@pytest.mark.anyio
async def test_the_poll_that_was_told_to_slow_down_is_recorded_before_the_refusal() -> None:
    storage = Storage()
    clock = make_clock()
    grant, _, _ = _grant(storage, clock)
    issued = await _issued(grant)
    device_code = str(issued["device_code"])
    with pytest.raises(OAuthServerError):
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=device_code),
            RecordingResponseType(),
            _AN_HOUR,
        )
    clock.sleep(1)

    with pytest.raises(OAuthServerError):
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=device_code),
            RecordingResponseType(),
            _AN_HOUR,
        )

    polled = storage.device_codes.codes[device_code].get_last_polled_at()
    assert polled is not None
    assert polled == clock.now()


@pytest.mark.anyio
async def test_a_poll_after_the_interval_has_passed_is_told_to_keep_waiting() -> None:
    storage = Storage()
    clock = make_clock()
    grant, _, _ = _grant(storage, clock)
    issued = await _issued(grant)
    device_code = str(issued["device_code"])
    with pytest.raises(OAuthServerError):
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=device_code),
            RecordingResponseType(),
            _AN_HOUR,
        )
    clock.sleep(6)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=device_code),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "authorization_pending"


@pytest.mark.anyio
async def test_a_refused_device_is_told_so() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    issued = await _issued(grant)
    device_code = str(issued["device_code"])
    await grant.complete_device_authorization_request(device_code, "user-1", user_approved=False)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=device_code),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "access_denied"


@pytest.mark.anyio
async def test_an_approved_device_is_handed_a_token_pair() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read"))
    grant, dispatcher, _ = _grant(storage)
    device_code = await _approved_code(grant, storage)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(device_code=device_code),
        response_type,
        _AN_HOUR,
    )

    assert response_type.access_token is not None
    assert response_type.access_token.get_user_identifier() == "user-1"
    assert response_type.refresh_token is not None
    assert dispatcher.names()[-2:] == (
        RequestEvent.ACCESS_TOKEN_ISSUED,
        RequestEvent.REFRESH_TOKEN_ISSUED,
    )


@pytest.mark.anyio
async def test_the_scopes_are_finalised_for_the_owner_who_approved_the_device() -> None:
    storage = Storage(scopes=InMemoryScopeRepository("read"))
    grant, _, _ = _grant(storage)
    device_code = await _approved_code(grant, storage)

    _ = await grant.respond_to_access_token_request(
        _token_request(device_code=device_code),
        RecordingResponseType(),
        _AN_HOUR,
    )

    call = storage.scopes.finalized[-1]
    assert call.grant_type == _GRANT_TYPE
    assert call.user_identifier == "user-1"


@pytest.mark.anyio
async def test_a_device_code_is_spent_when_it_is_exchanged() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    device_code = await _approved_code(grant, storage)

    _ = await grant.respond_to_access_token_request(
        _token_request(device_code=device_code),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert await storage.device_codes.is_device_code_revoked(device_code) is True


@pytest.mark.anyio
async def test_a_device_code_cannot_be_exchanged_twice() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    device_code = await _approved_code(grant, storage)
    _ = await grant.respond_to_access_token_request(
        _token_request(device_code=device_code),
        RecordingResponseType(),
        _AN_HOUR,
    )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=device_code),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "revoked" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_token_request_carrying_no_device_code_is_refused() -> None:
    grant, _, _ = _grant(Storage())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "device_code" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_device_code_nobody_issued_is_refused_and_announced() -> None:
    grant, dispatcher, _ = _grant(Storage())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code="nobody"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_grant"
    assert dispatcher.names() == (RequestEvent.USER_AUTHENTICATION_FAILED,)


@pytest.mark.anyio
async def test_an_expired_device_code_ends_the_session() -> None:
    storage = Storage()
    clock = make_clock()
    grant, _, _ = _grant(storage, clock)
    issued = await _issued(grant)
    clock.sleep(601)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(device_code=str(issued["device_code"])),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "expired_token"


@pytest.mark.anyio
async def test_a_device_code_issued_to_another_client_is_refused() -> None:
    storage = Storage()
    grant, _, _ = _grant(storage)
    storage.clients.add(make_client("client-2"), "other")
    device_code = await _approved_code(grant, storage)
    request = server_request(
        "POST",
        "/token",
        parsed_body={
            "client_id": "client-2",
            "client_secret": "other",
            "device_code": device_code,
        },
    )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            request,
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "not issued to this client" in str(refusal.value.get_hint())
