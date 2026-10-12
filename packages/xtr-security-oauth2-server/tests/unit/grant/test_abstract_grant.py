"""Everything every grant does the same way: authenticate, validate, issue."""

from __future__ import annotations

import base64
from datetime import timedelta
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entities import make_client, make_scope
from tests.support.grants import Storage, wire
from tests.support.messages import server_request
from tests.support.repositories import InMemoryRefreshTokenRepository, InMemoryScopeRepository
from tests.support.response_types import RecordingResponseType
from tests.support.signing import FROZEN_NOW, make_clock
from xtr_security_oauth2_server.entities.traits.client_trait import ClientTrait
from xtr_security_oauth2_server.entities.traits.entity_trait import EntityTrait
from xtr_security_oauth2_server.exception import UniqueTokenIdentifierConstraintViolationError
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.grant.abstract_grant import AbstractGrant
from xtr_security_oauth2_server.grant.grant_type_interface import GrantTypeInterface
from xtr_security_oauth2_server.request_event import RequestEvent
from xtr_security_oauth2_server.request_types.authorization_request import AuthorizationRequest

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

_AN_HOUR = timedelta(hours=1)
_A_MONTH = timedelta(days=30)
_CALLBACK = "https://client.example.com/callback"


@final
class _PlainGrant(AbstractGrant):
    """The smallest grant there is: a name, and an answer of nothing new."""

    @override
    def get_identifier(self) -> str:
        return "stub"

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        return response_type


@final
class _RestrictedClient(EntityTrait, ClientTrait):
    """A client whose registration lets it use one grant, and none of ours."""

    @override
    def supports_grant_type(self, grant_type: str) -> bool:
        return grant_type == "something_else"


def _request(headers: dict[str, str] | None = None, **body: str) -> ServerRequestInterface:
    return server_request("POST", "/token", headers=headers or {}, parsed_body=body)


def _basic(user: str, password: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{user}:{password}".encode()).decode()

    return {"Authorization": f"Basic {encoded}"}


def _restricted_client(identifier: str = "client-1") -> _RestrictedClient:
    client = _RestrictedClient()
    client.set_identifier(identifier)
    client._name = "Restricted"
    client._redirect_uri = _CALLBACK

    return client


def _grant(storage: Storage | None = None) -> tuple[_PlainGrant, Storage, RecordingEventDispatcher]:
    held = storage if storage is not None else Storage()
    dispatcher = RecordingEventDispatcher()
    grant = _PlainGrant(dispatcher, make_clock())
    wire(grant, held)

    return grant, held, dispatcher


def test_a_grant_satisfies_the_grant_contract() -> None:
    assert GrantTypeInterface in AbstractGrant.__mro__
    assert isinstance(_PlainGrant(RecordingEventDispatcher(), make_clock()), GrantTypeInterface)


def test_it_answers_a_token_request_naming_its_own_grant_type() -> None:
    grant, _, _ = _grant()

    assert grant.can_respond_to_access_token_request(_request(grant_type="stub")) is True


def test_it_does_not_answer_a_token_request_naming_another_grant_type() -> None:
    grant, _, _ = _grant()

    assert grant.can_respond_to_access_token_request(_request(grant_type="password")) is False


def test_it_does_not_answer_a_token_request_naming_no_grant_type() -> None:
    grant, _, _ = _grant()

    assert grant.can_respond_to_access_token_request(_request()) is False


def test_an_ordinary_grant_answers_no_authorization_request() -> None:
    grant, _, _ = _grant()

    assert grant.can_respond_to_authorization_request(_request()) is False


def test_an_ordinary_grant_answers_no_device_authorization_request() -> None:
    grant, _, _ = _grant()

    assert grant.can_respond_to_device_authorization_request(_request()) is False


@pytest.mark.anyio
async def test_validating_an_authorization_request_says_this_grant_cannot() -> None:
    grant, _, _ = _grant()

    with pytest.raises(InvalidArgumentError, match="authorization request"):
        _ = await grant.validate_authorization_request(_request())


@pytest.mark.anyio
async def test_completing_an_authorization_request_says_this_grant_cannot() -> None:
    grant, _, _ = _grant()

    with pytest.raises(InvalidArgumentError, match="authorization request"):
        _ = await grant.complete_authorization_request(_request(), AuthorizationRequest())


@pytest.mark.anyio
async def test_answering_a_device_authorization_request_says_this_grant_cannot() -> None:
    grant, _, _ = _grant()

    with pytest.raises(InvalidArgumentError, match="device authorization request"):
        _ = await grant.respond_to_device_authorization_request(_request())


@pytest.mark.anyio
async def test_completing_a_device_authorization_request_says_this_grant_cannot() -> None:
    grant, _, _ = _grant()

    with pytest.raises(InvalidArgumentError, match="device authorization request"):
        await grant.complete_device_authorization_request(
            "device-1",
            "user-1",
            user_approved=True,
        )


def test_an_ordinary_grant_has_no_polling_interval_to_show() -> None:
    grant, _, _ = _grant()

    assert grant.get_interval_visibility() is False


def test_asking_an_ordinary_grant_to_show_its_interval_says_it_cannot() -> None:
    grant, _, _ = _grant()

    with pytest.raises(InvalidArgumentError, match="interval"):
        grant.set_interval_visibility(True)


def test_asking_an_ordinary_grant_for_a_pre_filled_uri_says_it_cannot() -> None:
    grant, _, _ = _grant()

    with pytest.raises(InvalidArgumentError, match="verification_uri_complete"):
        grant.set_include_verification_uri_complete(True)


def test_credentials_in_the_body_win_over_the_ones_in_the_header() -> None:
    grant, _, _ = _grant()
    request = _request(_basic("header-client", "header-secret"), client_id="body", secret="x")

    assert grant.get_client_credentials(request)[0] == "body"


def test_a_body_secret_wins_over_the_one_in_the_header() -> None:
    grant, _, _ = _grant()
    request = _request(_basic("c", "header-secret"), client_secret="body-secret")

    assert grant.get_client_credentials(request) == ("c", "body-secret")


def test_the_header_is_read_when_the_body_names_no_client() -> None:
    grant, _, _ = _grant()

    assert grant.get_client_credentials(_request(_basic("c", "s"))) == ("c", "s")


def test_a_request_naming_no_client_at_all_is_refused() -> None:
    grant, _, _ = _grant()

    with pytest.raises(OAuthServerError) as refusal:
        _ = grant.get_client_credentials(_request())

    assert refusal.value.get_error_type() == "invalid_request"
    assert "client_id" in str(refusal.value.get_hint())


def test_a_client_that_sent_no_secret_is_read_as_having_none() -> None:
    grant, _, _ = _grant()

    assert grant.get_client_credentials(_request(client_id="c")) == ("c", "")


def test_an_authorization_header_of_another_scheme_is_not_read() -> None:
    grant, _, _ = _grant()
    request = _request({"Authorization": "Bearer abc"}, client_id="c")

    assert grant.get_client_credentials(request) == ("c", "")


def test_an_authorization_header_that_is_not_base64_is_not_read() -> None:
    grant, _, _ = _grant()
    request = _request({"Authorization": "Basic not base64!"}, client_id="c")

    assert grant.get_client_credentials(request) == ("c", "")


def test_an_authorization_header_without_a_colon_is_not_read() -> None:
    encoded = base64.b64encode(b"nocolon").decode()
    grant, _, _ = _grant()
    request = _request({"Authorization": f"Basic {encoded}"}, client_id="c")

    assert grant.get_client_credentials(request) == ("c", "")


def test_an_authorization_header_naming_an_empty_user_is_not_read() -> None:
    grant, _, _ = _grant()
    request = _request(_basic("", "secret"), client_id="c")

    assert grant.get_client_credentials(request) == ("c", "")


@pytest.mark.anyio
async def test_a_confidential_client_with_the_right_secret_is_authenticated() -> None:
    storage = Storage()
    client = make_client("client-1")
    storage.clients.add(client, "secret")
    grant, _, dispatcher = _grant(storage)

    found = await grant.validate_client(_request(client_id="client-1", client_secret="secret"))

    assert found is client
    assert dispatcher.dispatched == []


@pytest.mark.anyio
async def test_a_confidential_client_that_sent_no_secret_is_told_what_is_missing() -> None:
    storage = Storage()
    storage.clients.add(make_client("client-1"), "secret")
    grant, _, dispatcher = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_client(_request(client_id="client-1"))

    assert refusal.value.get_error_type() == "invalid_request"
    assert "client_secret" in str(refusal.value.get_hint())
    assert dispatcher.dispatched == []


@pytest.mark.anyio
async def test_a_confidential_client_with_the_wrong_secret_is_refused_and_announced() -> None:
    storage = Storage()
    storage.clients.add(make_client("client-1"), "secret")
    grant, _, dispatcher = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_client(_request(client_id="client-1", client_secret="guess"))

    assert refusal.value.get_error_type() == "invalid_client"
    assert refusal.value.get_http_status_code() == 401
    assert dispatcher.names() == (RequestEvent.CLIENT_AUTHENTICATION_FAILED,)


@pytest.mark.anyio
async def test_an_unknown_client_is_refused_and_announced() -> None:
    grant, _, dispatcher = _grant()

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_client(_request(client_id="nobody", client_secret="s"))

    assert refusal.value.get_error_type() == "invalid_client"
    assert dispatcher.names() == (RequestEvent.CLIENT_AUTHENTICATION_FAILED,)


@pytest.mark.anyio
async def test_a_public_client_is_not_asked_for_a_secret() -> None:
    storage = Storage()
    client = make_client("client-1", confidential=False)
    storage.clients.add(client)
    grant, _, dispatcher = _grant(storage)

    assert await grant.validate_client(_request(client_id="client-1")) is client
    assert dispatcher.dispatched == []


@pytest.mark.anyio
async def test_a_client_not_registered_for_this_grant_is_refused_as_unauthorized() -> None:
    storage = Storage()
    storage.clients.add(_restricted_client())
    grant, _, _ = _grant(storage)

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.get_client_entity_or_fail("client-1", _request())

    assert refusal.value.get_error_type() == "unauthorized_client"


@pytest.mark.anyio
async def test_a_client_registered_for_this_grant_is_found() -> None:
    storage = Storage()
    client = make_client("client-1")
    storage.clients.add(client)
    grant, _, _ = _grant(storage)

    assert await grant.get_client_entity_or_fail("client-1", _request()) is client


@pytest.mark.anyio
async def test_a_registered_redirect_uri_is_accepted() -> None:
    grant, _, dispatcher = _grant()

    await grant.validate_redirect_uri(_CALLBACK, make_client(), _request())

    assert dispatcher.dispatched == []


@pytest.mark.anyio
async def test_an_unregistered_redirect_uri_is_refused_and_announced() -> None:
    grant, _, dispatcher = _grant()

    with pytest.raises(OAuthServerError) as refusal:
        await grant.validate_redirect_uri("https://evil.example.com/", make_client(), _request())

    assert refusal.value.get_error_type() == "invalid_client"
    assert dispatcher.names() == (RequestEvent.CLIENT_AUTHENTICATION_FAILED,)


@pytest.mark.anyio
async def test_a_scope_string_is_split_on_spaces() -> None:
    grant, _, _ = _grant(Storage(scopes=InMemoryScopeRepository("read", "write")))

    scopes = await grant.validate_scopes("read write")

    assert [scope.get_identifier() for scope in scopes] == ["read", "write"]


@pytest.mark.anyio
async def test_a_scope_string_of_only_spaces_asks_for_nothing() -> None:
    grant, _, _ = _grant(Storage(scopes=InMemoryScopeRepository("read")))

    assert await grant.validate_scopes("   ") == ()


@pytest.mark.anyio
async def test_no_scope_at_all_asks_for_nothing() -> None:
    grant, _, _ = _grant()

    assert await grant.validate_scopes(None) == ()


@pytest.mark.anyio
async def test_a_sequence_of_scope_names_is_looked_up_one_by_one() -> None:
    grant, _, _ = _grant(Storage(scopes=InMemoryScopeRepository("read", "write")))

    scopes = await grant.validate_scopes(["write", "read"])

    assert [scope.get_identifier() for scope in scopes] == ["write", "read"]


@pytest.mark.anyio
async def test_an_unknown_scope_is_refused_by_name() -> None:
    grant, _, _ = _grant(Storage(scopes=InMemoryScopeRepository("read")))

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_scopes("read delete")

    assert refusal.value.get_error_type() == "invalid_scope"
    assert "delete" in str(refusal.value.get_hint())


@pytest.mark.anyio
async def test_an_unknown_scope_is_refused_to_the_redirect_uri_it_was_asked_from() -> None:
    grant, _, _ = _grant()

    with pytest.raises(OAuthServerError) as refusal:
        _ = await grant.validate_scopes("delete", _CALLBACK)

    assert refusal.value.get_redirect_uri() == _CALLBACK


@pytest.mark.anyio
async def test_an_issued_access_token_expires_after_the_time_it_was_given() -> None:
    grant, storage, _ = _grant()

    token = await grant.issue_access_token(_AN_HOUR, make_client(), "user-1", ())

    assert token.get_expiry_date_time() == FROZEN_NOW + _AN_HOUR
    assert storage.access_tokens.tokens[token.get_identifier()] is token


@pytest.mark.anyio
async def test_an_issued_access_token_can_sign_itself() -> None:
    grant, _, _ = _grant()

    token = await grant.issue_access_token(_AN_HOUR, make_client(), "user-1", ())

    assert token.to_string().count(".") == 2


@pytest.mark.anyio
async def test_an_issued_access_token_carries_the_scopes_it_was_granted() -> None:
    grant, _, _ = _grant()

    token = await grant.issue_access_token(_AN_HOUR, make_client(), None, (make_scope("read"),))

    assert [scope.get_identifier() for scope in token.get_scopes()] == ["read"]


@pytest.mark.anyio
async def test_a_taken_access_token_identifier_is_tried_again_with_another() -> None:
    grant, storage, _ = _grant()
    storage.access_tokens.collisions.remaining = 9

    token = await grant.issue_access_token(_AN_HOUR, make_client(), "user-1", ())

    assert storage.access_tokens.tokens[token.get_identifier()] is token


@pytest.mark.anyio
async def test_a_tenth_taken_access_token_identifier_gives_up() -> None:
    grant, storage, _ = _grant()
    storage.access_tokens.collisions.remaining = 10

    with pytest.raises(UniqueTokenIdentifierConstraintViolationError):
        _ = await grant.issue_access_token(_AN_HOUR, make_client(), "user-1", ())


@pytest.mark.anyio
async def test_an_issued_authorization_code_remembers_what_it_was_issued_for() -> None:
    grant, storage, _ = _grant()
    grant.set_auth_code_repository(storage.auth_codes)
    client = make_client()

    code = await grant.issue_auth_code(
        timedelta(minutes=10),
        client,
        "user-1",
        _CALLBACK,
        (make_scope("read"),),
    )

    assert code.get_client() is client
    assert code.get_user_identifier() == "user-1"
    assert code.get_redirect_uri() == _CALLBACK
    assert code.get_expiry_date_time() == FROZEN_NOW + timedelta(minutes=10)
    assert storage.auth_codes.codes[code.get_identifier()] is code


@pytest.mark.anyio
async def test_an_authorization_code_asked_for_without_a_redirect_uri_names_none() -> None:
    grant, storage, _ = _grant()
    grant.set_auth_code_repository(storage.auth_codes)

    code = await grant.issue_auth_code(timedelta(minutes=10), make_client(), "user-1", None, ())

    assert code.get_redirect_uri() is None


@pytest.mark.anyio
async def test_a_refresh_token_is_tied_to_the_access_token_it_came_with() -> None:
    grant, storage, _ = _grant()
    grant.set_refresh_token_repository(storage.refresh_tokens)
    grant.set_refresh_token_ttl(_A_MONTH)
    access_token = await grant.issue_access_token(_AN_HOUR, make_client(), "user-1", ())

    refresh_token = await grant.issue_refresh_token(access_token)

    assert refresh_token is not None
    assert refresh_token.get_access_token() is access_token
    assert refresh_token.get_expiry_date_time() == FROZEN_NOW + _A_MONTH
    assert storage.refresh_tokens.tokens[refresh_token.get_identifier()] is refresh_token


@pytest.mark.anyio
async def test_no_refresh_token_is_issued_when_the_repository_mints_none() -> None:
    storage = Storage(refresh_tokens=InMemoryRefreshTokenRepository(issues=False))
    grant, _, _ = _grant(storage)
    grant.set_refresh_token_repository(storage.refresh_tokens)
    grant.set_refresh_token_ttl(_A_MONTH)
    access_token = await grant.issue_access_token(_AN_HOUR, make_client(), "user-1", ())

    assert await grant.issue_refresh_token(access_token) is None


@pytest.mark.anyio
async def test_no_refresh_token_is_issued_to_a_client_not_registered_for_them() -> None:
    grant, storage, _ = _grant()
    grant.set_refresh_token_repository(storage.refresh_tokens)
    grant.set_refresh_token_ttl(_A_MONTH)
    access_token = await grant.issue_access_token(_AN_HOUR, _restricted_client(), "user-1", ())

    assert await grant.issue_refresh_token(access_token) is None


def test_a_generated_identifier_is_eighty_hexadecimal_characters() -> None:
    grant, _, _ = _grant()

    identifier = grant.generate_unique_identifier()

    assert len(identifier) == 80
    assert int(identifier, 16) >= 0


def test_two_generated_identifiers_differ() -> None:
    grant, _, _ = _grant()

    assert grant.generate_unique_identifier() != grant.generate_unique_identifier()


def test_asking_for_an_identifier_of_no_length_is_refused() -> None:
    grant, _, _ = _grant()

    with pytest.raises(OAuthServerError, match="random"):
        _ = grant.generate_unique_identifier(0)


@pytest.mark.anyio
async def test_a_grant_without_a_client_repository_names_the_setter() -> None:
    grant = _PlainGrant(RecordingEventDispatcher(), make_clock())

    with pytest.raises(InvalidArgumentError, match="set_client_repository"):
        _ = await grant.validate_client(_request(client_id="c", client_secret="s"))


@pytest.mark.anyio
async def test_a_grant_without_a_scope_repository_names_the_setter() -> None:
    grant = _PlainGrant(RecordingEventDispatcher(), make_clock())

    with pytest.raises(InvalidArgumentError, match="set_scope_repository"):
        _ = await grant.validate_scopes("read")


@pytest.mark.anyio
async def test_a_grant_without_an_access_token_repository_names_the_setter() -> None:
    grant = _PlainGrant(RecordingEventDispatcher(), make_clock())

    with pytest.raises(InvalidArgumentError, match="set_access_token_repository"):
        _ = await grant.issue_access_token(_AN_HOUR, make_client(), None, ())


@pytest.mark.anyio
async def test_a_grant_without_a_signing_key_names_the_setter() -> None:
    storage = Storage()
    grant = _PlainGrant(RecordingEventDispatcher(), make_clock())
    grant.set_access_token_repository(storage.access_tokens)

    with pytest.raises(InvalidArgumentError, match="set_private_key"):
        _ = await grant.issue_access_token(_AN_HOUR, make_client(), None, ())


@pytest.mark.anyio
async def test_a_grant_without_an_auth_code_repository_names_the_setter() -> None:
    grant = _PlainGrant(RecordingEventDispatcher(), make_clock())

    with pytest.raises(InvalidArgumentError, match="set_auth_code_repository"):
        _ = await grant.issue_auth_code(_AN_HOUR, make_client(), "user-1", None, ())


@pytest.mark.anyio
async def test_a_grant_without_a_refresh_token_repository_names_the_setter() -> None:
    grant, _, _ = _grant()
    access_token = await grant.issue_access_token(_AN_HOUR, make_client(), "user-1", ())

    with pytest.raises(InvalidArgumentError, match="set_refresh_token_repository"):
        _ = await grant.issue_refresh_token(access_token)


@pytest.mark.anyio
async def test_a_grant_without_a_refresh_token_lifetime_names_the_setter() -> None:
    grant, storage, _ = _grant()
    grant.set_refresh_token_repository(storage.refresh_tokens)
    access_token: AccessTokenEntityInterface = await grant.issue_access_token(
        _AN_HOUR,
        make_client(),
        "user-1",
        (),
    )

    with pytest.raises(InvalidArgumentError, match="set_refresh_token_ttl"):
        _ = await grant.issue_refresh_token(access_token)


def test_a_grant_without_a_default_scope_names_the_setter() -> None:
    grant = _PlainGrant(RecordingEventDispatcher(), make_clock())

    with pytest.raises(InvalidArgumentError, match="set_default_scope"):
        _ = grant._default_scope_or_fail()


def test_a_grant_without_a_user_repository_names_the_setter() -> None:
    grant = _PlainGrant(RecordingEventDispatcher(), make_clock())

    with pytest.raises(InvalidArgumentError, match="set_user_repository"):
        _ = grant._user_repository_or_fail()


@pytest.mark.anyio
async def test_a_grant_answers_the_response_type_it_was_handed() -> None:
    grant, _, _ = _grant()
    response_type = RecordingResponseType()

    answered = await grant.respond_to_access_token_request(_request(), response_type, _AN_HOUR)

    assert answered is response_type


def test_its_reading_names_the_grant_and_nothing_it_holds() -> None:
    grant, _, _ = _grant()

    shown = repr(grant)

    assert "stub" in shown
    assert "_PlainGrant" in shown
    assert "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8" not in shown
