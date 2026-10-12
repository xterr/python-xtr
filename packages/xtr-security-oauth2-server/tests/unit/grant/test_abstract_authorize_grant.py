"""What the two grants that send a browser somewhere share."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.entities import make_client
from tests.support.signing import make_clock
from xtr_security_oauth2_server.grant.abstract_authorize_grant import AbstractAuthorizeGrant
from xtr_security_oauth2_server.request_types.authorization_request_interface import (
    AuthorizationRequestInterface,
)

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

_CALLBACK = "https://client.example.com/callback"


@final
class _PlainAuthorizeGrant(AbstractAuthorizeGrant):
    """The smallest grant that sends a browser somewhere."""

    @override
    def get_identifier(self) -> str:
        return "stub_authorize"

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        return response_type


def _grant() -> _PlainAuthorizeGrant:
    return _PlainAuthorizeGrant(RecordingEventDispatcher(), make_clock())


def test_it_appends_the_parameters_as_a_query() -> None:
    built = _grant().make_redirect_uri(_CALLBACK, {"code": "abc"})

    assert built == f"{_CALLBACK}?code=abc"


def test_it_joins_on_to_a_uri_that_already_carries_a_query() -> None:
    built = _grant().make_redirect_uri(f"{_CALLBACK}?kept=1", {"code": "abc"})

    assert built == f"{_CALLBACK}?kept=1&code=abc"


def test_it_leaves_out_a_parameter_that_has_no_value() -> None:
    built = _grant().make_redirect_uri(_CALLBACK, {"code": "abc", "state": None})

    assert built == f"{_CALLBACK}?code=abc"


def test_it_encodes_what_a_query_cannot_carry_as_it_stands() -> None:
    built = _grant().make_redirect_uri(_CALLBACK, {"state": "a b&c"})

    assert built == f"{_CALLBACK}?state=a+b%26c"


def test_it_can_be_told_to_build_a_fragment_instead() -> None:
    built = _grant().make_redirect_uri(_CALLBACK, {"access_token": "abc"}, "#")

    assert built == f"{_CALLBACK}#access_token=abc"


def test_it_joins_on_to_a_uri_that_already_carries_a_fragment() -> None:
    built = _grant().make_redirect_uri(f"{_CALLBACK}#kept", {"access_token": "abc"}, "#")

    assert built == f"{_CALLBACK}#kept&access_token=abc"


def test_it_still_marks_the_query_when_there_is_nothing_to_put_in_it() -> None:
    assert _grant().make_redirect_uri(_CALLBACK) == f"{_CALLBACK}?"


def test_it_writes_a_number_out_as_a_parameter() -> None:
    built = _grant().make_redirect_uri(_CALLBACK, {"expires_in": 3600})

    assert built == f"{_CALLBACK}?expires_in=3600"


def test_it_starts_a_fresh_authorization_request_each_time() -> None:
    grant = _grant()

    first = grant.create_authorization_request()
    second = grant.create_authorization_request()

    assert isinstance(first, AuthorizationRequestInterface)
    assert first is not second


def test_a_client_with_one_registered_uri_is_answered_at_it() -> None:
    client = make_client(redirect_uri=_CALLBACK)

    assert _grant().get_client_redirect_uri(client) == _CALLBACK


def test_a_client_with_several_registered_uris_is_answered_at_the_first() -> None:
    client = make_client(redirect_uri=[_CALLBACK, "https://client.example.com/other"])

    assert _grant().get_client_redirect_uri(client) == _CALLBACK
