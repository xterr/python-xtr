"""Reading a named parameter out of a request message."""

from __future__ import annotations

from tests.support.messages import make_message
from xtr_security_http._request_parameters import (
    header_parameter,
    payload_parameter,
    query_parameter,
)


def test_a_payload_parameter_is_read_from_the_parsed_body() -> None:
    request = make_message(parsed_body={"_token": "abc"})

    assert payload_parameter(request, "_token") == "abc"


def test_an_absent_payload_parameter_answers_the_default() -> None:
    request = make_message(parsed_body={"other": "x"})

    assert payload_parameter(request, "_token") is None
    assert payload_parameter(request, "_token", "fallback") == "fallback"


def test_a_body_that_parsed_to_no_parameters_answers_the_default() -> None:
    request = make_message(parsed_body=["not", "a", "mapping"])

    assert payload_parameter(request, "_token") is None


def test_a_query_parameter_is_read_from_the_query_string() -> None:
    request = make_message(query="_token=abc")

    assert query_parameter(request, "_token") == "abc"


def test_an_absent_query_parameter_answers_the_default() -> None:
    request = make_message(query="other=x")

    assert query_parameter(request, "_token") is None
    assert query_parameter(request, "_token", "fallback") == "fallback"


def test_a_header_parameter_is_read_from_the_header() -> None:
    request = make_message(headers={"X-CSRF-Token": "abc"})

    assert header_parameter(request, "X-CSRF-Token") == "abc"


def test_an_absent_header_answers_the_default() -> None:
    request = make_message()

    assert header_parameter(request, "X-CSRF-Token") is None
    assert header_parameter(request, "X-CSRF-Token", "fallback") == "fallback"


def test_a_header_set_to_nothing_answers_the_default() -> None:
    request = make_message(headers={"X-CSRF-Token": ""})

    assert header_parameter(request, "X-CSRF-Token") is None
