"""A code handed to the browser is redeemed by the client for a token."""

from __future__ import annotations

import base64
import hashlib
from datetime import timedelta
from typing import TYPE_CHECKING, final
from urllib.parse import parse_qs, urlsplit

import pytest
from typing_extensions import override
from xtr_http_message import Response

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.encryption import seal, unseal
from tests.support.entities import make_client, make_user
from tests.support.grants import Storage, wire
from tests.support.messages import server_request
from tests.support.repositories import InMemoryRefreshTokenRepository, InMemoryScopeRepository
from tests.support.response_types import RecordingResponseType
from tests.support.signing import FROZEN_NOW, make_clock
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.grant.auth_code_grant import AuthCodeGrant
from xtr_security_oauth2_server_core.request_event import RequestEvent

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_oauth2_server_core.entities.auth_code_entity_interface import (
        AuthCodeEntityInterface,
    )
    from xtr_security_oauth2_server_core.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )

_AN_HOUR = timedelta(hours=1)
_TEN_MINUTES = timedelta(minutes=10)
_CALLBACK = "https://client.example.com/callback"
_VERIFIER = "a" * 43
_CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(_VERIFIER.encode()).digest()).rstrip(b"=").decode()
)


@final
class _GrantCarryingANonce(AuthCodeGrant):
    """What an add-on writes to carry one more thing across the consent step."""

    @override
    def get_auth_code_payload(
        self,
        auth_code: AuthCodeEntityInterface,
        authorization_request: AuthorizationRequestInterface,
    ) -> dict[str, object]:
        payload = super().get_auth_code_payload(auth_code, authorization_request)
        payload["nonce"] = "n-0S6_WzA2Mj"

        return payload


def _authorize_request(**query: str) -> ServerRequestInterface:
    return server_request("GET", "/authorize", query_params=query)


def _token_request(**body: str) -> ServerRequestInterface:
    return server_request(
        "POST",
        "/token",
        parsed_body={"client_id": "client-1", "client_secret": "secret", **body},
    )


def _grant(
    storage: Storage,
    grant_class: type[AuthCodeGrant] = AuthCodeGrant,
) -> tuple[AuthCodeGrant, RecordingEventDispatcher]:
    dispatcher = RecordingEventDispatcher()
    grant = grant_class(
        dispatcher,
        make_clock(),
        storage.auth_codes,
        storage.refresh_tokens,
        _TEN_MINUTES,
    )
    wire(grant, storage)

    return grant, dispatcher


def _confidential(storage: Storage, redirect_uri: str | list[str] = _CALLBACK) -> None:
    storage.clients.add(make_client("client-1", redirect_uri=redirect_uri), "secret")


def _known_scopes() -> Storage:
    return Storage(scopes=InMemoryScopeRepository("read", "write"))


def _code_in(answer: ResponseInterface) -> str:
    query = parse_qs(urlsplit(answer.get_header_line("location")).query)

    return query["code"][0]


async def _approved_code(grant: AuthCodeGrant, **query: str) -> str:
    authorization_request = await grant.validate_authorization_request(
        _authorize_request(client_id="client-1", response_type="code", **query),
    )
    authorization_request.set_user(make_user("user-1"))
    authorization_request.set_authorization_approved(True)
    answered = await grant.complete_authorization_request(
        _authorize_request(),
        authorization_request,
    )

    return _code_in(await answered.generate_http_response(Response()))


def test_it_is_asked_for_by_name() -> None:
    grant, _ = _grant(Storage())

    assert grant.get_identifier() == "authorization_code"


def test_it_answers_an_authorization_request_asking_for_a_code() -> None:
    grant, _ = _grant(Storage())
    request = _authorize_request(response_type="code", client_id="client-1")

    assert grant.can_respond_to_authorization_request(request) is True


def test_it_does_not_answer_an_authorization_request_asking_for_a_token() -> None:
    grant, _ = _grant(Storage())
    request = _authorize_request(response_type="token", client_id="client-1")

    assert grant.can_respond_to_authorization_request(request) is False


def test_it_does_not_answer_an_authorization_request_naming_no_client() -> None:
    grant, _ = _grant(Storage())

    assert grant.can_respond_to_authorization_request(_authorize_request(response_type="code")) is (
        False
    )


@pytest.mark.anyio
async def test_a_validated_request_records_what_was_asked_for() -> None:
    storage = _known_scopes()
    _confidential(storage)
    grant, _ = _grant(storage)

    authorization_request = await grant.validate_authorization_request(
        _authorize_request(
            response_type="code",
            client_id="client-1",
            redirect_uri=_CALLBACK,
            state="xyz",
            scope="read",
        ),
    )

    assert authorization_request.get_grant_type_id() == "authorization_code"
    assert authorization_request.get_client().get_identifier() == "client-1"
    assert authorization_request.get_redirect_uri() == _CALLBACK
    assert authorization_request.get_state() == "xyz"
    assert [scope.get_identifier() for scope in authorization_request.get_scopes()] == ["read"]


@pytest.mark.anyio
async def test_an_authorization_request_naming_no_client_is_refused() -> None:
    grant, _ = _grant(Storage())

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_authorization_request(_authorize_request(response_type="code"))

    assert "client_id" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_the_client_may_name_itself_in_the_authorization_header() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    encoded = base64.b64encode(b"client-1:secret").decode()
    request = server_request(
        "GET",
        "/authorize",
        headers={"Authorization": f"Basic {encoded}"},
        query_params={"response_type": "code"},
    )

    authorization_request = await grant.validate_authorization_request(request)

    assert authorization_request.get_client().get_identifier() == "client-1"


@pytest.mark.anyio
async def test_an_unregistered_redirect_uri_is_refused_and_announced() -> None:
    storage = Storage()
    _confidential(storage)
    grant, dispatcher = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_authorization_request(
            _authorize_request(
                response_type="code",
                client_id="client-1",
                redirect_uri="https://evil.example.com/",
            ),
        )

    assert refusal.value.get_error_type() == "invalid_client"
    assert refusal.value.get_redirect_uri() is None
    assert dispatcher.names() == (RequestEvent.CLIENT_AUTHENTICATION_FAILED,)


@pytest.mark.anyio
async def test_a_client_with_one_registered_uri_need_not_name_it() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)

    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="code", client_id="client-1"),
    )

    assert authorization_request.get_redirect_uri() is None


@pytest.mark.anyio
async def test_a_client_with_several_registered_uris_must_name_one() -> None:
    storage = Storage()
    _confidential(storage, [_CALLBACK, "https://client.example.com/other"])
    grant, dispatcher = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_authorization_request(
            _authorize_request(response_type="code", client_id="client-1"),
        )

    assert refusal.value.get_error_type() == "invalid_client"
    assert dispatcher.names() == (RequestEvent.CLIENT_AUTHENTICATION_FAILED,)


@pytest.mark.anyio
async def test_an_unknown_scope_is_refused_to_the_client_with_its_state() -> None:
    storage = _known_scopes()
    _confidential(storage)
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_authorization_request(
            _authorize_request(
                response_type="code",
                client_id="client-1",
                scope="delete",
                state="xyz",
            ),
        )

    assert refusal.value.get_error_type() == "invalid_scope"
    assert refusal.value.get_redirect_uri() == f"{_CALLBACK}?state=xyz"


@pytest.mark.anyio
async def test_a_code_challenge_is_recorded_with_the_method_it_was_made_by() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)

    authorization_request = await grant.validate_authorization_request(
        _authorize_request(
            response_type="code",
            client_id="client-1",
            code_challenge=_CHALLENGE,
            code_challenge_method="S256",
        ),
    )

    assert authorization_request.get_code_challenge() == _CHALLENGE
    assert authorization_request.get_code_challenge_method() == "S256"


@pytest.mark.anyio
async def test_a_code_challenge_named_without_a_method_is_read_as_plain() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)

    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="code", client_id="client-1", code_challenge=_VERIFIER),
    )

    assert authorization_request.get_code_challenge_method() == "plain"


@pytest.mark.anyio
async def test_a_code_challenge_method_this_server_cannot_judge_is_refused() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_authorization_request(
            _authorize_request(
                response_type="code",
                client_id="client-1",
                code_challenge=_CHALLENGE,
                code_challenge_method="S512",
            ),
        )

    assert "S256" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_malformed_code_challenge_is_refused() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_authorization_request(
            _authorize_request(response_type="code", client_id="client-1", code_challenge="short"),
        )

    assert "RFC-7636" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_public_client_must_bring_a_code_challenge() -> None:
    storage = Storage()
    storage.clients.add(make_client("client-1", confidential=False))
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_authorization_request(
            _authorize_request(response_type="code", client_id="client-1"),
        )

    assert "public clients" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_public_client_need_not_when_the_deployment_turned_that_off() -> None:
    storage = Storage()
    storage.clients.add(make_client("client-1", confidential=False))
    grant, _ = _grant(storage)
    grant.disable_require_code_challenge_for_public_clients()

    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="code", client_id="client-1"),
    )

    assert authorization_request.get_code_challenge() is None


@pytest.mark.anyio
async def test_a_confidential_client_need_not_bring_a_code_challenge() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)

    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="code", client_id="client-1"),
    )

    assert authorization_request.get_code_challenge() is None


@pytest.mark.anyio
async def test_an_approved_request_sends_the_browser_back_with_a_code_and_the_state() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)

    code = await _approved_code(grant, redirect_uri=_CALLBACK, state="xyz")
    payload = unseal(code)

    assert payload["client_id"] == "client-1"
    assert payload["redirect_uri"] == _CALLBACK
    assert payload["user_id"] == "user-1"
    assert payload["expire_time"] == int((FROZEN_NOW + _TEN_MINUTES).timestamp())


@pytest.mark.anyio
async def test_the_state_is_handed_back_unchanged() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="code", client_id="client-1", state="xyz"),
    )
    authorization_request.set_user(make_user("user-1"))
    authorization_request.set_authorization_approved(True)

    answered = await grant.complete_authorization_request(
        _authorize_request(),
        authorization_request,
    )
    answer = await answered.generate_http_response(Response())
    location = answer.get_header_line("location")

    assert parse_qs(urlsplit(location).query)["state"] == ["xyz"]


@pytest.mark.anyio
async def test_the_code_carries_the_scopes_and_the_challenge_it_was_asked_with() -> None:
    storage = _known_scopes()
    _confidential(storage)
    grant, _ = _grant(storage)

    code = await _approved_code(
        grant,
        scope="read write",
        code_challenge=_CHALLENGE,
        code_challenge_method="S256",
    )
    payload = unseal(code)

    assert payload["scopes"] == ["read", "write"]
    assert payload["code_challenge"] == _CHALLENGE
    assert payload["code_challenge_method"] == "S256"


@pytest.mark.anyio
async def test_a_subclass_carries_one_more_thing_across_the_consent_step() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage, _GrantCarryingANonce)

    code = await _approved_code(grant)

    assert unseal(code)["nonce"] == "n-0S6_WzA2Mj"


@pytest.mark.anyio
async def test_a_refused_request_sends_the_browser_back_with_the_refusal() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="code", client_id="client-1", state="xyz"),
    )
    authorization_request.set_user(make_user("user-1"))

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.complete_authorization_request(
            _authorize_request(),
            authorization_request,
        )

    assert refusal.value.get_error_type() == "access_denied"
    assert refusal.value.get_redirect_uri() == f"{_CALLBACK}?state=xyz"


@pytest.mark.anyio
async def test_completing_a_request_nobody_decided_on_names_the_missing_user() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    authorization_request = await grant.validate_authorization_request(
        _authorize_request(response_type="code", client_id="client-1"),
    )

    with pytest.raises(InvalidArgumentError, match="resource owner"):
        _ = await grant.complete_authorization_request(
            _authorize_request(),
            authorization_request,
        )


@pytest.mark.anyio
async def test_a_code_is_redeemed_for_an_access_token_and_a_refresh_token() -> None:
    storage = _known_scopes()
    _confidential(storage)
    grant, dispatcher = _grant(storage)
    code = await _approved_code(grant, scope="read")
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(code=code),
        response_type,
        _AN_HOUR,
    )

    assert response_type.access_token is not None
    assert response_type.access_token.get_user_identifier() == "user-1"
    assert response_type.refresh_token is not None
    assert dispatcher.names() == (
        RequestEvent.ACCESS_TOKEN_ISSUED,
        RequestEvent.REFRESH_TOKEN_ISSUED,
    )


@pytest.mark.anyio
async def test_the_scopes_are_finalised_for_the_owner_and_the_code_they_came_from() -> None:
    storage = _known_scopes()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant, scope="read")

    _ = await grant.respond_to_access_token_request(
        _token_request(code=code),
        RecordingResponseType(),
        _AN_HOUR,
    )

    call = storage.scopes.finalized[-1]
    assert call.grant_type == "authorization_code"
    assert call.user_identifier == "user-1"
    assert call.auth_code_id == unseal(code)["auth_code_id"]


@pytest.mark.anyio
async def test_a_redeemed_code_is_revoked() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant)

    _ = await grant.respond_to_access_token_request(
        _token_request(code=code),
        RecordingResponseType(),
        _AN_HOUR,
    )

    assert await storage.auth_codes.is_auth_code_revoked(str(unseal(code)["auth_code_id"])) is True


@pytest.mark.anyio
async def test_a_code_cannot_be_redeemed_twice() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant)
    _ = await grant.respond_to_access_token_request(
        _token_request(code=code),
        RecordingResponseType(),
        _AN_HOUR,
    )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code=code),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_grant"
    assert "revoked" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_token_request_carrying_no_code_is_refused() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "code" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_code_this_server_did_not_seal_is_refused() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code="not-a-sealed-code"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "decrypting" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_code_naming_no_code_is_refused_as_malformed() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    sealed = seal({"client_id": "client-1", "expire_time": 99999999999})

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code=sealed),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "malformed" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_an_expired_code_is_refused() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    sealed = seal(
        {
            "client_id": "client-1",
            "auth_code_id": "code-1",
            "expire_time": int((FROZEN_NOW - timedelta(seconds=1)).timestamp()),
            "scopes": [],
            "user_id": "user-1",
            "redirect_uri": None,
        },
    )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code=sealed),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "expired" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_code_issued_to_another_client_is_refused() -> None:
    storage = Storage()
    _confidential(storage)
    storage.clients.add(make_client("client-2"), "other")
    grant, _ = _grant(storage)
    code = await _approved_code(grant)
    request = server_request(
        "POST",
        "/token",
        parsed_body={"client_id": "client-2", "client_secret": "other", "code": code},
    )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            request,
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "not issued to this client" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_code_issued_for_a_redirect_uri_must_be_redeemed_naming_it() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant, redirect_uri=_CALLBACK)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code=code),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "redirect_uri" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_code_redeemed_naming_another_redirect_uri_is_refused() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant, redirect_uri=_CALLBACK)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code=code, redirect_uri="https://evil.example.com/"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "Invalid redirect URI" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_code_redeemed_naming_the_same_redirect_uri_is_accepted() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant, redirect_uri=_CALLBACK)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(code=code, redirect_uri=_CALLBACK),
        response_type,
        _AN_HOUR,
    )

    assert response_type.access_token is not None


@pytest.mark.anyio
async def test_a_code_challenge_is_redeemed_with_the_verifier_it_was_made_from() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant, code_challenge=_CHALLENGE, code_challenge_method="S256")
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(code=code, code_verifier=_VERIFIER),
        response_type,
        _AN_HOUR,
    )

    assert response_type.access_token is not None


@pytest.mark.anyio
async def test_another_verifier_does_not_redeem_the_code() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant, code_challenge=_CHALLENGE, code_challenge_method="S256")

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code=code, code_verifier="b" * 43),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_grant"
    assert "code_verifier" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_code_with_a_challenge_is_not_redeemed_without_a_verifier() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant, code_challenge=_CHALLENGE, code_challenge_method="S256")

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code=code),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "invalid_request"
    assert "code_verifier" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_malformed_verifier_is_refused() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant, code_challenge=_CHALLENGE, code_challenge_method="S256")

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code=code, code_verifier="short"),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "RFC-7636" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_verifier_sent_for_a_code_with_no_challenge_is_refused() -> None:
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    code = await _approved_code(grant)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code=code, code_verifier=_VERIFIER),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert "no code_challenge" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_a_code_naming_a_challenge_method_this_server_cannot_judge_is_a_server_error() -> (
    None
):
    storage = Storage()
    _confidential(storage)
    grant, _ = _grant(storage)
    sealed = seal(
        {
            "client_id": "client-1",
            "auth_code_id": "code-1",
            "expire_time": int((FROZEN_NOW + _TEN_MINUTES).timestamp()),
            "scopes": [],
            "user_id": "user-1",
            "redirect_uri": None,
            "code_challenge": _CHALLENGE,
            "code_challenge_method": "S512",
        },
    )

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.respond_to_access_token_request(
            _token_request(code=sealed, code_verifier=_VERIFIER),
            RecordingResponseType(),
            _AN_HOUR,
        )

    assert refusal.value.get_error_type() == "server_error"


@pytest.mark.anyio
async def test_no_refresh_token_is_handed_out_when_the_repository_mints_none() -> None:
    storage = Storage(refresh_tokens=InMemoryRefreshTokenRepository(issues=False))
    _confidential(storage)
    grant, dispatcher = _grant(storage)
    code = await _approved_code(grant)
    response_type = RecordingResponseType()

    _ = await grant.respond_to_access_token_request(
        _token_request(code=code),
        response_type,
        _AN_HOUR,
    )

    assert response_type.refresh_token is None
    assert dispatcher.names() == (RequestEvent.ACCESS_TOKEN_ISSUED,)
