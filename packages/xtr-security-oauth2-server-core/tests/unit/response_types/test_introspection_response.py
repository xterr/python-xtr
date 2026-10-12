"""What is said about a token asked about: whether it is live, and what it carries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_http_message import Response

from tests.support.messages import document_of
from xtr_security_oauth2_server_core.response_types.introspection_response import (
    IntrospectionResponse,
)
from xtr_security_oauth2_server_core.response_types.introspection_response_type_interface import (
    IntrospectionResponseTypeInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface


@final
class _IntrospectionResponseWithParams(IntrospectionResponse):
    """A document for a deployment that publishes fields of its own."""

    @override
    def get_extra_params(
        self,
        token_type: str,
        token_data: Mapping[str, object],
    ) -> Mapping[str, object]:
        del token_type

        return {"foo": "bar", "extended": token_data["extension"]}


def _moment(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _body(answer: ResponseInterface) -> Mapping[str, object]:
    return cast("Mapping[str, object]", document_of(answer))


def test_it_declares_the_contract_a_question_is_answered_through() -> None:
    assert IntrospectionResponseTypeInterface in IntrospectionResponse.__mro__


def test_an_access_token_is_published_claim_by_claim() -> None:
    response_type = IntrospectionResponse()
    response_type.set_active(True)
    response_type.set_token_type("access_token")
    response_type.set_token_data(
        {
            "scopes": ["scope1", "scope2"],
            "aud": ["client1"],
            "username": "username1",
            "exp": _moment(123456),
            "iat": 111111,
            "nbf": "654321",
            "sub": "user1",
            "iss": "https://example.com",
            "jti": "token1",
        },
    )

    answer = response_type.generate_http_response(Response())

    assert answer.get_status_code() == 200
    assert answer.get_header_line("cache-control") == "no-store"
    assert answer.get_header_line("content-type") == "application/json; charset=UTF-8"
    assert _body(answer) == {
        "active": True,
        "scope": "scope1 scope2",
        "client_id": "client1",
        "username": "username1",
        "token_type": "Bearer",
        "exp": 123456,
        "iat": 111111,
        "nbf": 654321,
        "sub": "user1",
        "aud": ["client1"],
        "iss": "https://example.com",
        "jti": "token1",
    }


def test_a_refresh_token_is_published_out_of_its_sealed_payload() -> None:
    response_type = IntrospectionResponse()
    response_type.set_active(True)
    response_type.set_token_type("refresh_token")
    response_type.set_token_data(
        {
            "scopes": ["scope1", "scope2"],
            "client_id": "client1",
            "expire_time": _moment(123456),
            "user_id": "user1",
            "refresh_token_id": "token1",
        },
    )

    answer = response_type.generate_http_response(Response())

    assert answer.get_status_code() == 200
    assert answer.get_header_line("cache-control") == "no-store"
    assert answer.get_header_line("content-type") == "application/json; charset=UTF-8"
    assert _body(answer) == {
        "active": True,
        "scope": "scope1 scope2",
        "client_id": "client1",
        "exp": 123456,
        "sub": "user1",
        "jti": "token1",
    }


def test_a_token_that_is_not_live_is_published_as_nothing_but_that() -> None:
    response_type = IntrospectionResponse()
    response_type.set_active(False)
    response_type.set_token_type("access_token")
    response_type.set_token_data({"scopes": ["scope1", "scope2"], "client_id": "client1"})

    answer = response_type.generate_http_response(Response())

    assert answer.get_status_code() == 200
    assert answer.get_header_line("cache-control") == "no-store"
    assert answer.get_header_line("content-type") == "application/json; charset=UTF-8"
    assert _body(answer) == {"active": False}


def test_a_deployment_may_publish_fields_of_its_own() -> None:
    response_type = _IntrospectionResponseWithParams()
    response_type.set_active(True)
    response_type.set_token_type("access_token")
    response_type.set_token_data(
        {
            "scopes": ["scope1", "scope2"],
            "client_id": "client1",
            "jti": None,
            "extension": "extension1",
        },
    )

    answer = response_type.generate_http_response(Response())

    assert answer.get_status_code() == 200
    assert answer.get_header_line("cache-control") == "no-store"
    assert answer.get_header_line("content-type") == "application/json; charset=UTF-8"
    assert _body(answer) == {
        "active": True,
        "scope": "scope1 scope2",
        "client_id": "client1",
        "token_type": "Bearer",
        "foo": "bar",
        "extended": "extension1",
    }


def test_a_kind_of_token_it_knows_nothing_about_is_published_as_live_and_no_more() -> None:
    response_type = IntrospectionResponse()
    response_type.set_active(True)
    response_type.set_token_type("saml2_token")
    response_type.set_token_data({"jti": "token1"})

    answer = response_type.generate_http_response(Response())

    assert _body(answer) == {"active": True}


def test_an_instant_it_cannot_read_leaves_its_field_out() -> None:
    response_type = IntrospectionResponse()
    response_type.set_active(True)
    response_type.set_token_type("access_token")
    response_type.set_token_data({"jti": "token1", "exp": "whenever"})

    assert "exp" not in _body(response_type.generate_http_response(Response()))


def test_its_reading_says_whether_the_token_is_live_and_never_what_it_says() -> None:
    response_type = IntrospectionResponse()
    response_type.set_active(True)
    response_type.set_token_type("access_token")
    response_type.set_token_data({"jti": "access-1", "sub": "user-1"})

    shown = repr(response_type)

    assert shown == "IntrospectionResponse(active=True)"
