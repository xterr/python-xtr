from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

import pytest
from xtr_http_message_contracts import (
    RequestInterface,
    ResponseInterface,
    ServerRequestInterface,
    StreamInterface,
    UploadedFileInterface,
    UploadError,
    UriInterface,
)
from xtr_http_message_contracts.factory import (
    RequestFactoryInterface,
    ResponseFactoryInterface,
    ServerRequestFactoryInterface,
    StreamFactoryInterface,
    UploadedFileFactoryInterface,
    UriFactoryInterface,
)

from xtr_http_message.exception import InvalidArgumentError, StreamError
from xtr_http_message.factory.http_factory import HttpFactory
from xtr_http_message.uri import Uri

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "interface",
    [
        pytest.param(RequestFactoryInterface, id="request"),
        pytest.param(ResponseFactoryInterface, id="response"),
        pytest.param(ServerRequestFactoryInterface, id="server_request"),
        pytest.param(StreamFactoryInterface, id="stream"),
        pytest.param(UploadedFileFactoryInterface, id="uploaded_file"),
        pytest.param(UriFactoryInterface, id="uri"),
    ],
)
def test_the_factory_is_every_one_of_the_six_factories(interface: type) -> None:
    assert interface in HttpFactory.__mro__


def test_a_response_asked_for_by_code_alone_brings_the_recommended_phrase() -> None:
    assert HttpFactory().create_response(200).get_reason_phrase() == "OK"


def test_a_response_asked_for_with_an_empty_phrase_carries_none() -> None:
    assert HttpFactory().create_response(200, "").get_reason_phrase() == ""


def test_a_response_asked_for_with_a_phrase_carries_that_phrase() -> None:
    assert HttpFactory().create_response(200, "Foo").get_reason_phrase() == "Foo"


def test_a_code_with_no_recommended_phrase_asked_for_alone_carries_none() -> None:
    assert HttpFactory().create_response(567).get_reason_phrase() == ""


def test_a_code_with_no_recommended_phrase_and_an_empty_phrase_is_still_that_code() -> None:
    response = HttpFactory().create_response(567, "")

    assert (response.get_status_code(), response.get_reason_phrase()) == (567, "")


def test_a_code_with_no_recommended_phrase_keeps_the_phrase_it_was_given() -> None:
    response = HttpFactory().create_response(567, "Foo")

    assert (response.get_status_code(), response.get_reason_phrase()) == (567, "Foo")


def test_a_response_asked_for_with_nothing_is_an_empty_two_hundred() -> None:
    response = HttpFactory().create_response()

    assert (response.get_status_code(), response.get_reason_phrase()) == (200, "OK")


def test_a_response_is_a_response() -> None:
    assert isinstance(HttpFactory().create_response(), ResponseInterface)


def test_a_request_is_built_for_the_method_and_uri_it_was_asked_for() -> None:
    request = HttpFactory().create_request("POST", "https://example.com/orders")

    assert (
        isinstance(request, RequestInterface),
        request.get_method(),
        str(request.get_uri()),
    ) == (True, "POST", "https://example.com/orders")


def test_a_request_may_be_asked_for_with_a_uri_rather_than_text() -> None:
    uri = Uri("https://example.com/orders")

    assert HttpFactory().create_request("GET", uri).get_uri() is uri


def test_a_server_request_is_built_for_the_method_and_uri_it_was_asked_for() -> None:
    request = HttpFactory().create_server_request("GET", "/orders?page=2")

    assert (
        isinstance(request, ServerRequestInterface),
        request.get_method(),
        request.get_query_params(),
    ) == (True, "GET", {"page": "2"})


def test_a_server_request_asked_for_with_no_environment_parameters_has_none() -> None:
    assert HttpFactory().create_server_request("GET", "/").get_server_params() == {}


def test_a_server_request_is_seeded_with_the_environment_parameters_it_was_given() -> None:
    params = {"REMOTE_ADDR": "203.0.113.7"}

    request = HttpFactory().create_server_request("GET", "/", params)

    assert request.get_server_params() == params


async def test_a_stream_is_built_over_the_bytes_it_was_asked_for() -> None:
    stream = HttpFactory().create_stream(b"Hello")

    assert (isinstance(stream, StreamInterface), await stream.get_contents()) == (True, b"Hello")


async def test_a_stream_asked_for_with_nothing_is_empty() -> None:
    assert await HttpFactory().create_stream().get_contents() == b""


async def test_a_stream_is_built_over_the_file_it_was_asked_for(tmp_path: Path) -> None:
    path = tmp_path / "body.txt"
    _ = path.write_bytes(b"Hello")

    stream = HttpFactory().create_stream_from_file(str(path))

    try:
        assert await stream.get_contents() == b"Hello"
    finally:
        await stream.close()


async def test_a_stream_over_a_file_opened_to_write_can_be_written_to(tmp_path: Path) -> None:
    path = tmp_path / "body.txt"

    stream = HttpFactory().create_stream_from_file(str(path), "w")

    try:
        assert await stream.write(b"Hello") == 5
    finally:
        await stream.close()

    assert path.read_bytes() == b"Hello"


def test_a_stream_over_a_file_asked_for_with_no_path_is_refused() -> None:
    with pytest.raises(StreamError, match="Path cannot be empty"):
        _ = HttpFactory().create_stream_from_file("")


def test_a_stream_over_a_file_that_is_not_there_is_refused(tmp_path: Path) -> None:
    missing = str(tmp_path / "gone.txt")

    with pytest.raises(StreamError, match=re.escape(f'The file "{missing}" cannot be opened')):
        _ = HttpFactory().create_stream_from_file(missing)


def test_a_stream_asked_for_in_a_mode_that_is_not_one_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "body.txt"
    _ = path.write_bytes(b"Hello")

    with pytest.raises(InvalidArgumentError, match=re.escape('The mode "q" is invalid.')):
        _ = HttpFactory().create_stream_from_file(str(path), "q")


async def test_a_stream_is_built_over_the_file_object_it_was_asked_for() -> None:
    with io.BytesIO(b"Hello") as file:
        stream = HttpFactory().create_stream_from_resource(file)

        assert (await stream.get_contents(), stream.detach() is file) == (b"Hello", True)


async def test_an_uploaded_file_is_built_over_the_stream_it_was_asked_for() -> None:
    factory = HttpFactory()

    upload = factory.create_uploaded_file(factory.create_stream(b"Hello"))

    assert (
        isinstance(upload, UploadedFileInterface),
        await upload.get_stream().get_contents(),
    ) == (
        True,
        b"Hello",
    )


def test_an_uploaded_file_asked_for_with_no_size_takes_it_off_the_stream() -> None:
    factory = HttpFactory()

    upload = factory.create_uploaded_file(factory.create_stream(b"Hello"))

    assert upload.get_size() == 5


def test_an_uploaded_file_keeps_the_size_it_was_given() -> None:
    factory = HttpFactory()

    upload = factory.create_uploaded_file(factory.create_stream(b"Hello"), 3)

    assert upload.get_size() == 3


def test_an_uploaded_file_asked_for_with_nothing_else_went_through() -> None:
    factory = HttpFactory()

    upload = factory.create_uploaded_file(factory.create_stream(b"Hello"))

    assert (
        upload.get_error(),
        upload.get_client_filename(),
        upload.get_client_media_type(),
    ) == (UploadError.OK, None, None)


def test_an_uploaded_file_keeps_what_the_client_sent() -> None:
    factory = HttpFactory()

    upload = factory.create_uploaded_file(
        factory.create_stream(b"Hello"),
        5,
        UploadError.OK,
        "greeting.txt",
        "text/plain",
    )

    assert (upload.get_client_filename(), upload.get_client_media_type()) == (
        "greeting.txt",
        "text/plain",
    )


def test_an_uploaded_file_can_be_built_for_an_upload_that_did_not_go_through() -> None:
    factory = HttpFactory()

    upload = factory.create_uploaded_file(factory.create_stream(), 0, UploadError.NO_FILE)

    assert upload.get_error() == UploadError.NO_FILE


def test_a_uri_is_built_from_the_text_it_was_asked_for() -> None:
    uri = HttpFactory().create_uri("https://example.com/orders?page=2")

    assert (isinstance(uri, UriInterface), str(uri)) == (
        True,
        "https://example.com/orders?page=2",
    )


def test_a_uri_asked_for_with_nothing_has_no_component() -> None:
    assert str(HttpFactory().create_uri()) == ""


def test_a_uri_that_cannot_be_read_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="Unable to parse URI"):
        _ = HttpFactory().create_uri("http://")
