from __future__ import annotations

import pytest
from xtr_http_message_contracts import ResponseInterface, StreamInterface

from xtr_http_message.exception import InvalidArgumentError
from xtr_http_message.factory.http_factory import HttpFactory
from xtr_http_message.response import Response

pytestmark = pytest.mark.anyio


def test_response_is_a_response() -> None:
    assert ResponseInterface in Response.__mro__


async def test_a_response_built_with_nothing_is_an_empty_two_hundred() -> None:
    response = Response()

    assert (
        response.get_status_code(),
        response.get_protocol_version(),
        response.get_reason_phrase(),
        response.get_headers(),
        await response.get_body().get_contents(),
    ) == (200, "1.1", "OK", {}, b"")


def test_the_body_of_a_response_built_with_nothing_is_still_a_stream() -> None:
    assert isinstance(Response().get_body(), StreamInterface)


async def test_a_body_given_to_the_constructor_is_read_from_its_beginning() -> None:
    assert await Response(200, None, b"Hello").get_body().get_contents() == b"Hello"


def test_a_status_code_brings_its_recommended_phrase_with_it() -> None:
    response = Response(404)

    assert (response.get_status_code(), response.get_reason_phrase()) == (404, "Not Found")


def test_a_status_code_with_no_recommended_phrase_carries_none() -> None:
    response = Response(999)

    assert (response.get_status_code(), response.get_reason_phrase()) == (999, "")


def test_an_empty_reason_phrase_is_kept_empty() -> None:
    response = Response(404, None, None, "1.1", "")

    assert (response.get_status_code(), response.get_reason_phrase()) == (404, "")


def test_the_constructor_does_not_read_the_body_it_is_given() -> None:
    body = HttpFactory().create_stream(b"Hello")

    response = Response(200, None, body)

    assert (response.get_body() is body, body.tell()) == (True, 0)


def test_a_header_given_as_one_value_is_recorded_as_one() -> None:
    response = Response(200, {"Foo": "Bar"})

    assert (
        response.get_headers(),
        response.get_header_line("Foo"),
        response.get_header("Foo"),
    ) == ({"Foo": ["Bar"]}, "Bar", ["Bar"])


def test_a_header_given_as_several_values_is_recorded_as_several() -> None:
    response = Response(200, {"Foo": ["baz", "bar"]})

    assert (
        response.get_headers(),
        response.get_header_line("Foo"),
        response.get_header("Foo"),
    ) == ({"Foo": ["baz", "bar"]}, "baz, bar", ["baz", "bar"])


async def test_a_body_given_to_the_constructor_is_the_body() -> None:
    assert await Response(200, None, b"baz").get_body().get_contents() == b"baz"


async def test_no_body_given_to_the_constructor_is_an_empty_body() -> None:
    assert await Response(200, None, None).get_body().get_contents() == b""


async def test_a_body_of_one_zero_is_still_a_body() -> None:
    assert await Response(200, None, b"0").get_body().get_contents() == b"0"


def test_a_reason_phrase_given_to_the_constructor_is_the_phrase() -> None:
    assert Response(200, None, None, "1.1", "bar").get_reason_phrase() == "bar"


def test_a_reason_phrase_of_one_zero_is_still_a_phrase() -> None:
    assert Response(200, None, None, "1.1", "0").get_reason_phrase() == "0"


def test_a_protocol_version_given_to_the_constructor_is_the_version() -> None:
    assert Response(200, None, None, "1000").get_protocol_version() == "1000"


def test_a_status_set_afterwards_brings_its_recommended_phrase_with_it() -> None:
    response = Response().with_status(201)

    assert (response.get_status_code(), response.get_reason_phrase()) == (201, "Created")


def test_a_status_set_afterwards_with_a_phrase_carries_that_phrase() -> None:
    response = Response().with_status(201, "Foo")

    assert (response.get_status_code(), response.get_reason_phrase()) == (201, "Foo")


def test_a_phrase_of_one_zero_set_afterwards_is_still_a_phrase() -> None:
    response = Response().with_status(201, "0")

    assert (response.get_status_code(), response.get_reason_phrase()) == (201, "0")


@pytest.mark.parametrize("code", [99, 600])
def test_a_status_outside_the_three_digit_range_is_refused(code: int) -> None:
    expected = (
        f"Status code has to be an integer between 100 and 599. A status code of {code} was given"
    )

    with pytest.raises(InvalidArgumentError, match=expected):
        _ = Response().with_status(code)


@pytest.mark.parametrize("code", [100, 599])
def test_a_status_at_the_edge_of_the_range_is_accepted(code: int) -> None:
    assert Response().with_status(code).get_status_code() == code


def test_a_protocol_version_set_afterwards_is_the_version() -> None:
    assert Response().with_protocol_version("1000").get_protocol_version() == "1000"


def test_setting_the_protocol_version_it_already_has_hands_the_same_response_back() -> None:
    response = Response()

    assert response.with_protocol_version("1.1") is response


async def test_a_body_set_afterwards_is_the_body() -> None:
    body = HttpFactory().create_stream(b"0")

    assert await Response().with_body(body).get_body().get_contents() == b"0"


def test_setting_the_body_it_already_reads_hands_the_same_response_back() -> None:
    response = Response()

    assert response.with_body(response.get_body()) is response


def test_a_header_set_afterwards_is_added_to_the_rest() -> None:
    response = Response(200, {"Foo": "Bar"}).with_header("baZ", "Bam")

    assert (
        response.get_headers(),
        response.get_header_line("baz"),
        response.get_header("baz"),
    ) == ({"Foo": ["Bar"], "baZ": ["Bam"]}, "Bam", ["Bam"])


def test_setting_a_header_leaves_the_response_it_was_asked_of_alone() -> None:
    response = Response(200, {"Foo": "Bar"})

    _ = response.with_header("baZ", "Bam")

    assert response.get_headers() == {"Foo": ["Bar"]}


def test_a_header_set_afterwards_as_several_values_holds_them_all() -> None:
    response = Response(200, {"Foo": "Bar"}).with_header("baZ", ["Bam", "Bar"])

    assert (
        response.get_headers(),
        response.get_header_line("baz"),
        response.get_header("baz"),
    ) == ({"Foo": ["Bar"], "baZ": ["Bam", "Bar"]}, "Bam, Bar", ["Bam", "Bar"])


def test_setting_a_header_replaces_the_one_recorded_under_another_case() -> None:
    response = Response(200, {"Foo": "Bar"}).with_header("foO", "Bam")

    assert (
        response.get_headers(),
        response.get_header_line("foo"),
        response.get_header("foo"),
    ) == ({"foO": ["Bam"]}, "Bam", ["Bam"])


def test_an_added_header_goes_after_what_the_header_already_held() -> None:
    response = Response(200, {"Foo": "Bar"}).with_added_header("foO", "Baz")

    assert (
        response.get_headers(),
        response.get_header_line("foo"),
        response.get_header("foo"),
    ) == ({"Foo": ["Bar", "Baz"]}, "Bar, Baz", ["Bar", "Baz"])


def test_adding_a_header_leaves_the_response_it_was_asked_of_alone() -> None:
    response = Response(200, {"Foo": "Bar"})

    _ = response.with_added_header("foO", "Baz")

    assert response.get_headers() == {"Foo": ["Bar"]}


def test_several_added_values_all_go_after_what_the_header_held() -> None:
    response = Response(200, {"Foo": "Bar"}).with_added_header("foO", ["Baz", "Bam"])

    assert (
        response.get_headers(),
        response.get_header_line("foo"),
        response.get_header("foo"),
    ) == ({"Foo": ["Bar", "Baz", "Bam"]}, "Bar, Baz, Bam", ["Bar", "Baz", "Bam"])


def test_adding_a_header_the_response_does_not_carry_records_it() -> None:
    response = Response(200, {"Foo": "Bar"}).with_added_header("nEw", "Baz")

    assert (
        response.get_headers(),
        response.get_header_line("new"),
        response.get_header("new"),
    ) == ({"Foo": ["Bar"], "nEw": ["Baz"]}, "Baz", ["Baz"])


def test_removing_a_header_recorded_under_another_case_removes_it() -> None:
    response = Response(200, {"Foo": "Bar", "Baz": "Bam"}).without_header("foO")

    assert (response.has_header("foo"), response.get_headers()) == (False, {"Baz": ["Bam"]})


def test_removing_a_header_leaves_the_response_it_was_asked_of_alone() -> None:
    response = Response(200, {"Foo": "Bar", "Baz": "Bam"})

    _ = response.without_header("foO")

    assert (response.has_header("foo"), response.get_headers()) == (
        True,
        {"Foo": ["Bar"], "Baz": ["Bam"]},
    )


def test_removing_a_header_the_response_does_not_carry_hands_the_same_one_back() -> None:
    response = Response(200, {"Baz": "Bam"})

    assert response.without_header("foO") is response


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(Response(200, {"OWS": " \t \tFoo\t \t "}), id="constructor"),
        pytest.param(Response().with_header("OWS", " \t \tFoo\t \t "), id="with_header"),
        pytest.param(
            Response().with_added_header("OWS", " \t \tFoo\t \t "),
            id="with_added_header",
        ),
    ],
)
def test_the_blanks_around_a_header_value_are_not_part_of_it(response: ResponseInterface) -> None:
    assert (
        response.get_headers(),
        response.get_header_line("OWS"),
        response.get_header("OWS"),
    ) == ({"OWS": ["Foo"]}, "Foo", ["Foo"])


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        pytest.param(
            "foo",
            [],
            "Header values must be a string or an array of strings, empty array given",
            id="no-values",
        ),
        pytest.param("", "foo", "Header name must be an RFC 7230 compatible string", id="empty"),
        pytest.param(
            "Content-Type\r\n\r\n",
            "foo",
            "Header name must be an RFC 7230 compatible string",
            id="two-breaks-after",
        ),
        pytest.param(
            "Content-Type\r\n",
            "foo",
            "Header name must be an RFC 7230 compatible string",
            id="break-after",
        ),
        pytest.param(
            "Content-Type\n",
            "foo",
            "Header name must be an RFC 7230 compatible string",
            id="newline-after",
        ),
        pytest.param(
            "\r\nContent-Type",
            "foo",
            "Header name must be an RFC 7230 compatible string",
            id="break-before",
        ),
        pytest.param(
            "\nContent-Type",
            "foo",
            "Header name must be an RFC 7230 compatible string",
            id="newline-before",
        ),
        pytest.param(
            "\n",
            "foo",
            "Header name must be an RFC 7230 compatible string",
            id="newline",
        ),
        pytest.param(
            "\r\n",
            "foo",
            "Header name must be an RFC 7230 compatible string",
            id="break",
        ),
        pytest.param("\t", "foo", "Header name must be an RFC 7230 compatible string", id="tab"),
    ],
)
def test_a_header_that_is_not_one_is_refused(
    name: str,
    value: str | list[str],
    message: str,
) -> None:
    with pytest.raises(InvalidArgumentError, match=message):
        _ = Response().with_header(name, value)
