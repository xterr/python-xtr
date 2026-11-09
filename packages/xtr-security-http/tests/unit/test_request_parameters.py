"""Reading a named parameter out of a request message."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from tests.support.messages import make_message
from tests.support.served import served_message
from xtr_security_http._request_parameters import (
    header_parameter,
    payload_parameter,
    query_parameter,
    read_payload,
)

pytestmark = pytest.mark.anyio

_FORM = "application/x-www-form-urlencoded"


async def test_a_payload_parameter_is_read_from_the_parsed_body() -> None:
    request = make_message(parsed_body={"_token": "abc"})

    assert await payload_parameter(request, "_token") == "abc"


async def test_an_absent_payload_parameter_answers_the_default() -> None:
    request = make_message(parsed_body={"other": "x"})

    assert await payload_parameter(request, "_token") is None
    assert await payload_parameter(request, "_token", "fallback") == "fallback"


async def test_a_body_that_parsed_to_no_parameters_answers_the_default() -> None:
    request = make_message(parsed_body=["not", "a", "mapping"])

    assert await payload_parameter(request, "_token") is None


async def test_a_payload_parameter_is_read_from_a_served_form() -> None:
    request, _channel = served_message("POST", "/", b"_token=abc", content_type=_FORM)

    assert await payload_parameter(request, "_token") == "abc"


async def test_a_payload_parameter_leaves_a_served_body_that_is_no_form_unread() -> None:
    request, channel = served_message(
        "POST", "/", b"_token=abc", content_type="application/octet-stream"
    )

    assert await payload_parameter(request, "_token") is None
    assert channel.reads == 0


async def test_a_served_form_is_read_before_what_it_parsed_into_is_answered() -> None:
    request, _channel = served_message("POST", "/", b"_token=abc", content_type=_FORM)

    payload = await read_payload(request)

    assert isinstance(payload, Mapping)
    assert dict(payload) == {"_token": "abc"}  # pyright: ignore[reportUnknownArgumentType] -- a form maps names to what was sent


async def test_a_served_body_that_is_no_form_is_left_unread() -> None:
    request, channel = served_message(
        "POST", "/", b"_token=abc", content_type="application/octet-stream"
    )

    assert await read_payload(request) is None
    assert channel.reads == 0


async def test_what_an_eager_body_parsed_into_is_answered_whatever_its_media_type() -> None:
    request = make_message(method="POST", parsed_body={"_token": "abc"})

    assert await read_payload(request) == {"_token": "abc"}


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
