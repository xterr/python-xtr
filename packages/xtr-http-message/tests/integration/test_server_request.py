from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_http_message.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface, UploadedFileInterface


def test_the_environment_the_request_arrived_in_is_reported_as_it_was_given(
    server_request: ServerRequestInterface,
    server_params: Mapping[str, object],
) -> None:
    """The harness compares these with the table the language fills in for a request.

    There is no such table here: the environment is handed to the constructor,
    so what the suite handed it is what has to come back.
    """
    assert server_request.get_server_params() == server_params


def test_a_request_built_without_cookies_carries_none(
    server_request: ServerRequestInterface,
) -> None:
    """The harness compares these with the cookie table, which is empty off a server."""
    assert server_request.get_cookie_params() == {}


def test_the_cookies_can_be_replaced(server_request: ServerRequestInterface) -> None:
    replaced = server_request.with_cookie_params({"foo": "bar"})

    assert server_request.get_cookie_params() == {}
    assert replaced.get_cookie_params() == {"foo": "bar"}


def test_the_query_parameters_can_be_replaced(server_request: ServerRequestInterface) -> None:
    replaced = server_request.with_query_params({"foo": "bar"})

    assert server_request.get_query_params() == {}
    assert replaced.get_query_params() == {"foo": "bar"}


def test_the_uploaded_files_can_be_replaced(
    server_request: ServerRequestInterface,
    uploaded_file: UploadedFileInterface,
) -> None:
    """The harness passes a positional array of one file.

    The tree is keyed by the name a file was submitted under here, so the
    harness's array is ported as a single named entry.
    """
    replaced = server_request.with_uploaded_files({"file": uploaded_file})

    assert server_request.get_uploaded_files() == {}
    assert replaced.get_uploaded_files() == {"file": uploaded_file}


@pytest.mark.parametrize(
    "value",
    [None, object(), {"foo": "bar", "0": "baz"}],
    ids=["nothing parsed", "an object standing for the structure", "a mapping of parameters"],
)
def test_the_parsed_body_can_be_replaced(
    server_request: ServerRequestInterface,
    value: object | None,
) -> None:
    replaced = server_request.with_parsed_body(value)

    assert server_request.get_parsed_body() is None
    assert replaced.get_parsed_body() == value


@pytest.mark.parametrize(
    "value",
    [4711, 47.11, "foobar", True],
    ids=["an integer", "a number", "a string", "a boolean"],
)
def test_a_scalar_cannot_be_what_parsing_the_body_yielded(
    server_request: ServerRequestInterface,
    value: object,
) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = server_request.with_parsed_body(value)

    assert server_request.get_parsed_body() is None


def test_an_attribute_can_be_recorded_on_the_request(
    server_request: ServerRequestInterface,
) -> None:
    recorded = server_request.with_attribute("foo", "bar")

    assert server_request.get_attributes() == {}
    assert recorded.get_attributes() == {"foo": "bar"}


def test_a_second_attribute_joins_the_first(server_request: ServerRequestInterface) -> None:
    recorded = server_request.with_attribute("foo", "bar").with_attribute("baz", "biz")

    assert recorded.get_attributes() == {"foo": "bar", "baz": "biz"}


def test_one_attribute_is_read_back_on_its_own(server_request: ServerRequestInterface) -> None:
    assert server_request.with_attribute("foo", "bar").get_attribute("foo") == "bar"


def test_an_attribute_that_was_never_recorded_reads_as_the_default(
    server_request: ServerRequestInterface,
) -> None:
    recorded = server_request.with_attribute("foo", "bar")

    assert recorded.get_attribute("not found", "baz") == "baz"
    assert recorded.get_attribute("not found") is None


def test_an_attribute_can_be_removed(server_request: ServerRequestInterface) -> None:
    recorded = server_request.with_attribute("foo", "bar")

    without = recorded.without_attribute("foo")

    assert recorded.get_attribute("foo") == "bar"
    assert without.get_attribute("foo") is None
