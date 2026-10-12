"""The answer that sends a browser on to the client's redirect URI."""

from __future__ import annotations

import pytest
from xtr_http_message import Response

from tests.support.messages import body_of
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.response_types.redirect_response import RedirectResponse
from xtr_security_oauth2_server_core.response_types.response_type_interface import (
    ResponseTypeInterface,
)

_TARGET = "https://client.example.com/callback?code=abc&state=xyz"


def test_it_satisfies_the_response_type_contract() -> None:
    assert isinstance(RedirectResponse(), ResponseTypeInterface)


def test_it_answers_a_redirect_to_the_uri_it_was_given() -> None:
    response_type = RedirectResponse()
    response_type.set_redirect_uri(_TARGET)

    answer = response_type.generate_http_response(Response())

    assert answer.get_status_code() == 302
    assert answer.get_header_line("location") == _TARGET


def test_it_carries_nothing_but_the_redirect() -> None:
    response_type = RedirectResponse()
    response_type.set_redirect_uri(_TARGET)

    answer = response_type.generate_http_response(Response())

    assert body_of(answer) == ""
    assert set(answer.get_headers()) == {"Location"}


def test_answering_before_a_uri_is_set_names_the_setter() -> None:
    response_type = RedirectResponse()

    with pytest.raises(InvalidArgumentError, match="set_redirect_uri"):
        _ = response_type.generate_http_response(Response())
