from __future__ import annotations

from types import MappingProxyType

import pytest
from xtr_http_message_contracts import ServerRequestInterface, UploadError

from xtr_http_message.exception import InvalidArgumentError
from xtr_http_message.server_request import ServerRequest
from xtr_http_message.uploaded_file import UploadedFile

pytestmark = pytest.mark.anyio


def test_server_request_is_a_server_request() -> None:
    assert ServerRequestInterface in ServerRequest.__mro__


def test_a_server_request_built_with_nothing_carries_no_uploaded_file() -> None:
    assert ServerRequest("GET", "/").get_uploaded_files() == {}


def test_uploaded_files_set_afterwards_are_the_files() -> None:
    files = {"file": UploadedFile("test", 123, UploadError.OK)}

    assert ServerRequest("GET", "/").with_uploaded_files(files).get_uploaded_files() == files


def test_setting_uploaded_files_leaves_the_request_it_was_asked_of_alone() -> None:
    request = ServerRequest("GET", "/")

    changed = request.with_uploaded_files({"file": UploadedFile("test", 123, UploadError.OK)})

    assert (changed is not request, request.get_uploaded_files()) == (True, {})


def test_the_environment_parameters_are_taken_exactly_as_given() -> None:
    params = {"name": "value"}

    request = ServerRequest("GET", "/", None, None, "1.1", params)

    assert request.get_server_params() == params


def test_a_server_request_built_with_nothing_carries_no_environment_parameter() -> None:
    assert ServerRequest("GET", "/").get_server_params() == {}


def test_cookies_set_afterwards_are_the_cookies() -> None:
    params = {"name": "value"}

    assert ServerRequest("GET", "/").with_cookie_params(params).get_cookie_params() == params


def test_setting_cookies_leaves_the_request_it_was_asked_of_alone() -> None:
    request = ServerRequest("GET", "/")

    changed = request.with_cookie_params({"name": "value"})

    assert (changed is not request, request.get_cookie_params()) == (True, {})


def test_a_uri_with_no_query_string_leaves_the_query_parameters_empty() -> None:
    assert ServerRequest("GET", "/").get_query_params() == {}


@pytest.mark.parametrize(
    ("uri", "params"),
    [
        pytest.param("/?foo=bar", {"foo": "bar"}, id="one"),
        pytest.param("/?foo=bar&baz=bam", {"foo": "bar", "baz": "bam"}, id="two"),
        pytest.param("/?foo=", {"foo": ""}, id="no-value"),
        pytest.param("/?foo", {"foo": ""}, id="no-equals"),
        pytest.param("/?foo=bar&foo=baz", {"foo": "baz"}, id="repeated-last-wins"),
        pytest.param("/?a%20b=c%20d", {"a b": "c d"}, id="encoded"),
    ],
)
def test_the_query_parameters_are_read_off_the_uri(uri: str, params: dict[str, str]) -> None:
    assert ServerRequest("GET", uri).get_query_params() == params


def test_query_parameters_set_afterwards_are_the_parameters() -> None:
    params = {"name": "value"}

    assert ServerRequest("GET", "/?foo=bar").with_query_params(params).get_query_params() == params


def test_setting_query_parameters_leaves_the_request_it_was_asked_of_alone() -> None:
    request = ServerRequest("GET", "/?foo=bar")

    changed = request.with_query_params({"name": "value"})

    assert (changed is not request, request.get_query_params()) == (True, {"foo": "bar"})


def test_a_server_request_built_with_nothing_has_no_parsed_body() -> None:
    assert ServerRequest("GET", "/").get_parsed_body() is None


def test_a_parsed_body_set_afterwards_is_the_parsed_body() -> None:
    params = {"name": "value"}

    assert ServerRequest("GET", "/").with_parsed_body(params).get_parsed_body() == params


def test_setting_a_parsed_body_leaves_the_request_it_was_asked_of_alone() -> None:
    request = ServerRequest("GET", "/")

    changed = request.with_parsed_body({"name": "value"})

    assert (changed is not request, request.get_parsed_body()) == (True, None)


def test_a_parsed_body_may_be_an_object() -> None:
    parsed = object()

    assert ServerRequest("GET", "/").with_parsed_body(parsed).get_parsed_body() is parsed


def test_a_parsed_body_may_be_set_back_to_nothing() -> None:
    request = ServerRequest("GET", "/").with_parsed_body({"name": "value"})

    assert request.with_parsed_body(None).get_parsed_body() is None


@pytest.mark.parametrize(
    "data",
    [
        pytest.param("a string", id="str"),
        pytest.param(b"bytes", id="bytes"),
        pytest.param(7, id="int"),
        pytest.param(1.5, id="float"),
        pytest.param(True, id="bool"),
    ],
)
def test_a_parsed_body_that_is_a_scalar_is_refused(data: object) -> None:
    with pytest.raises(
        InvalidArgumentError,
        match="First parameter to with_parsed_body MUST be object, mapping or None",
    ):
        _ = ServerRequest("GET", "/").with_parsed_body(data)


def test_a_server_request_built_with_nothing_carries_no_attribute() -> None:
    request = ServerRequest("GET", "/")

    assert (request.get_attributes(), request.get_attribute("name")) == ({}, None)


def test_an_attribute_the_request_does_not_carry_reads_as_the_default() -> None:
    assert ServerRequest("GET", "/").get_attribute("name", "something") == "something"


def test_an_attribute_set_afterwards_is_the_attribute() -> None:
    request = ServerRequest("GET", "/").with_attribute("name", "value")

    assert (request.get_attribute("name"), request.get_attributes()) == (
        "value",
        {"name": "value"},
    )


def test_attributes_pile_up_as_they_are_set() -> None:
    request = ServerRequest("GET", "/").with_attribute("name", "value")

    assert request.with_attribute("other", "otherValue").get_attributes() == {
        "name": "value",
        "other": "otherValue",
    }


def test_setting_an_attribute_leaves_the_request_it_was_asked_of_alone() -> None:
    request = ServerRequest("GET", "/").with_attribute("name", "value")

    changed = request.with_attribute("other", "otherValue")

    assert (changed is not request, request.get_attributes()) == (True, {"name": "value"})


def test_removing_an_attribute_removes_only_that_one() -> None:
    request = (
        ServerRequest("GET", "/").with_attribute("name", "value").with_attribute("other", "another")
    )

    assert request.without_attribute("other").get_attributes() == {"name": "value"}


def test_removing_an_attribute_the_request_does_not_carry_hands_the_same_one_back() -> None:
    request = ServerRequest("GET", "/").with_attribute("name", "value")

    assert request.without_attribute("unknown") is request


def test_an_attribute_recorded_as_nothing_is_still_recorded() -> None:
    request = ServerRequest("GET", "/").with_attribute("name", None)

    assert request.get_attributes() == {"name": None}


def test_an_attribute_recorded_as_nothing_wins_over_the_default() -> None:
    request = ServerRequest("GET", "/").with_attribute("name", None)

    assert request.get_attribute("name", "different-default") is None


def test_removing_an_attribute_recorded_as_nothing_brings_the_default_back() -> None:
    request = ServerRequest("GET", "/").with_attribute("name", None)

    without = request.without_attribute("name")

    assert (without.get_attributes(), without.get_attribute("name", "different-default")) == (
        {},
        "different-default",
    )


def test_a_server_request_takes_its_host_header_from_the_uri() -> None:
    assert ServerRequest("GET", "http://foo.com:8124/bar").get_header_line("host") == "foo.com:8124"


def test_a_server_request_keeps_a_host_header_given_with_it() -> None:
    request = ServerRequest("GET", "http://foo.com/bar", {"Host": "a.com"})

    assert request.get_header_line("host") == "a.com"


async def test_a_body_given_to_a_server_request_is_its_body() -> None:
    assert await ServerRequest("GET", "/", None, b"baz").get_body().get_contents() == b"baz"


def test_environment_parameters_nothing_can_change_are_held_as_they_were_given() -> None:
    params = MappingProxyType({"name": "value"})

    request = ServerRequest("GET", "/", None, None, "1.1", params)

    assert request.get_server_params() is params


def test_environment_parameters_that_can_be_changed_are_copied() -> None:
    params: dict[str, object] = {"name": "value"}

    request = ServerRequest("GET", "/", None, None, "1.1", params)
    params["name"] = "other"

    assert request.get_server_params() == {"name": "value"}


def test_cookies_nothing_can_change_are_held_as_they_were_given() -> None:
    cookies = MappingProxyType({"name": "value"})

    request = ServerRequest("GET", "/").with_cookie_params(cookies)

    assert request.get_cookie_params() is cookies


def test_cookies_that_can_be_changed_are_copied() -> None:
    cookies = {"name": "value"}

    request = ServerRequest("GET", "/").with_cookie_params(cookies)
    cookies["name"] = "other"

    assert request.get_cookie_params() == {"name": "value"}


def test_query_parameters_nothing_can_change_are_held_as_they_were_given() -> None:
    params = MappingProxyType({"name": "value"})

    request = ServerRequest("GET", "/?foo=bar").with_query_params(params)

    assert request.get_query_params() is params


def test_query_parameters_that_can_be_changed_are_copied() -> None:
    params: dict[str, object] = {"name": "value"}

    request = ServerRequest("GET", "/").with_query_params(params)
    params["name"] = "other"

    assert request.get_query_params() == {"name": "value"}


def test_uploaded_files_nothing_can_change_are_held_as_they_were_given() -> None:
    files = MappingProxyType({"file": UploadedFile("test", 123, UploadError.OK)})

    request = ServerRequest("GET", "/").with_uploaded_files(files)

    assert request.get_uploaded_files() is files


def test_uploaded_files_that_can_be_changed_are_copied() -> None:
    files: dict[str, object] = {"file": UploadedFile("test", 123, UploadError.OK)}

    request = ServerRequest("GET", "/").with_uploaded_files(files)
    del files["file"]

    assert set(request.get_uploaded_files()) == {"file"}


def test_query_parameters_read_off_the_uri_are_copied_on_the_way_out() -> None:
    request = ServerRequest("GET", "/?foo=bar")

    first = request.get_query_params()

    assert (first, first is not request.get_query_params()) == ({"foo": "bar"}, True)
