"""The token document a client is handed at the end of a successful flow."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_http_message import Response

from tests.support.encryption import ENCRYPTION_KEY, unseal
from tests.support.entities import AccessToken, RefreshToken, make_client, make_scopes
from tests.support.messages import document_of
from tests.support.signing import FROZEN_NOW, make_clock, make_signer
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.response_types.bearer_token_response import BearerTokenResponse
from xtr_security_oauth2_server_core.response_types.response_type_interface import (
    ResponseTypeInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )

_AN_HOUR = timedelta(hours=1)
_A_MONTH = timedelta(days=30)


def _access_token(user_identifier: str | None = "user-1") -> AccessToken:
    token = AccessToken()
    token.set_identifier("access-1")
    token.set_client(make_client("client-1"))
    for scope in make_scopes("read", "write"):
        token.add_scope(scope)
    if user_identifier is not None:
        token.set_user_identifier(user_identifier)
    token.set_expiry_date_time(FROZEN_NOW + _AN_HOUR)
    token.set_private_key(make_signer())

    return token


def _refresh_token(access_token: AccessTokenEntityInterface) -> RefreshToken:
    token = RefreshToken()
    token.set_identifier("refresh-1")
    token.set_expiry_date_time(FROZEN_NOW + _A_MONTH)
    token.set_access_token(access_token)

    return token


def _response(access_token: AccessTokenEntityInterface | None = None) -> BearerTokenResponse:
    response_type = BearerTokenResponse(make_clock())
    response_type.set_encryption_key(ENCRYPTION_KEY, "key")
    if access_token is not None:
        response_type.set_access_token(access_token)

    return response_type


def _answered(response_type: BearerTokenResponse) -> Mapping[str, object]:
    return cast(
        "Mapping[str, object]",
        document_of(response_type.generate_http_response(Response())),
    )


@final
class _ResponseWithAnExtraField(BearerTokenResponse):
    @override
    def get_extra_params(self, access_token: AccessTokenEntityInterface) -> Mapping[str, object]:
        return {"issued_to": access_token.get_client().get_identifier()}


@final
class _ResponseWithShadowingExtras(BearerTokenResponse):
    @override
    def get_extra_params(self, access_token: AccessTokenEntityInterface) -> Mapping[str, object]:
        del access_token

        return {"token_type": "stolen", "extra": 1}


def test_it_is_a_response_type() -> None:
    assert isinstance(_response(), ResponseTypeInterface)


def test_it_names_the_token_type_the_bearer_scheme() -> None:
    assert _answered(_response(_access_token()))["token_type"] == "Bearer"


def test_it_says_how_many_seconds_the_token_has_left() -> None:
    assert _answered(_response(_access_token()))["expires_in"] == int(_AN_HOUR.total_seconds())


def test_it_carries_the_signed_access_token() -> None:
    access_token = _access_token()

    assert _answered(_response(access_token))["access_token"] == access_token.to_string()


def test_it_carries_no_refresh_token_when_none_was_issued() -> None:
    assert "refresh_token" not in _answered(_response(_access_token()))


def test_it_names_the_scope_the_token_was_granted() -> None:
    # "If the issued access token scope is different from the one requested by
    # the client, the authorization server MUST include the "scope" response
    # parameter" (RFC 6749 section 3.3); section 5.1 leaves it optional only
    # while the two are identical, so it is reported whenever there is one.
    assert _answered(_response(_access_token()))["scope"] == "read write"


def test_a_token_carrying_no_scope_names_none() -> None:
    # An empty ``scope`` is not a scope the standard can parse — a scope is one
    # name or more — so a token granted nothing leaves the field out.
    access_token = AccessToken()
    access_token.set_identifier("access-1")
    access_token.set_client(make_client("client-1"))
    access_token.set_expiry_date_time(FROZEN_NOW + _AN_HOUR)
    access_token.set_private_key(make_signer())

    assert "scope" not in _answered(_response(access_token))


def test_the_refresh_token_is_a_sealed_payload_naming_the_pair() -> None:
    access_token = _access_token()
    response_type = _response(access_token)
    response_type.set_refresh_token(_refresh_token(access_token))

    sealed = _answered(response_type)["refresh_token"]

    assert unseal(str(sealed)) == {
        "client_id": "client-1",
        "refresh_token_id": "refresh-1",
        "access_token_id": "access-1",
        "scopes": ["read", "write"],
        "user_id": "user-1",
        "expire_time": int((FROZEN_NOW + _A_MONTH).timestamp()),
    }


def test_a_token_issued_to_a_client_acting_for_itself_names_no_user() -> None:
    access_token = _access_token(None)
    response_type = _response(access_token)
    response_type.set_refresh_token(_refresh_token(access_token))

    sealed = _answered(response_type)["refresh_token"]

    assert unseal(str(sealed))["user_id"] is None


def test_it_answers_json_that_nothing_may_cache() -> None:
    answer = _response(_access_token()).generate_http_response(Response())

    assert answer.get_status_code() == 200
    assert answer.get_header_line("pragma") == "no-cache"
    assert answer.get_header_line("cache-control") == "no-store"
    assert answer.get_header_line("content-type") == "application/json; charset=UTF-8"


def test_the_document_is_written_into_the_body_as_bytes() -> None:
    answer = _response(_access_token()).generate_http_response(Response())

    written = bytes(answer.get_body())

    assert isinstance(written, bytes)
    assert json.loads(written.decode())["token_type"] == "Bearer"


def test_a_subclass_adds_fields_of_its_own() -> None:
    response_type = _ResponseWithAnExtraField(make_clock())
    response_type.set_encryption_key(ENCRYPTION_KEY, "key")
    response_type.set_access_token(_access_token())

    assert _answered(response_type)["issued_to"] == "client-1"


def test_it_preserves_flow_fields_when_extras_try_to_override_them() -> None:
    response_type = _ResponseWithShadowingExtras(make_clock())
    response_type.set_encryption_key(ENCRYPTION_KEY, "key")
    response_type.set_access_token(_access_token())

    body = _answered(response_type)

    assert body["token_type"] == "Bearer"
    assert body["extra"] == 1


def test_answering_before_an_access_token_is_set_names_the_setter() -> None:
    with pytest.raises(InvalidArgumentError, match="set_access_token"):
        _ = _response().generate_http_response(Response())
