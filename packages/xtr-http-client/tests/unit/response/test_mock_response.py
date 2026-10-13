from __future__ import annotations

import json
import re

import pytest
from xtr_http_message import Stream

from xtr_http_client import MockResponse
from xtr_http_client.exception import InvalidArgumentError, JsonError, TransportError

pytestmark = pytest.mark.anyio

URL = "https://example.com/file.json"


async def test_the_time_the_transfer_took_is_simulated_when_the_script_does_not_say() -> None:
    async with MockResponse(b"body").issue("GET", URL, {}) as response:
        total_time = response.get_info("total_time")

        assert isinstance(total_time, float)
        assert total_time > 0.0


async def test_the_time_the_script_says_the_transfer_took_is_the_time_it_took() -> None:
    written = MockResponse(b"body", {"total_time": 4.2})

    async with written.issue("GET", URL, {}) as response:
        assert response.get_info("total_time") == 4.2


async def test_the_body_decodes_as_the_json_document_it_was_written_as() -> None:
    document = {"color": "orange", "size": 42}

    async with MockResponse(json.dumps(document)).issue("GET", URL, {}) as response:
        assert await response.to_array() == document


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"", "Response body is empty."),
        (b"not json", f'for "{URL}".'),
        (b"[1,2}", f'for "{URL}".'),
        (b'"not an array"', f'an array, "str" returned for "{URL}".'),
        (b"8", f'an array, "int" returned for "{URL}".'),
    ],
    ids=["empty", "not json at all", "malformed", "a string", "a number"],
)
async def test_a_body_that_is_not_a_json_object_is_refused(body: bytes, message: str) -> None:
    async with MockResponse(body).issue("GET", URL, {}) as response:
        with pytest.raises(JsonError, match=re.escape(message)):
            _ = await response.to_array()


async def test_the_request_it_answered_is_readable_off_the_response() -> None:
    written = MockResponse(b"{}")
    url = "https://example.com/some-endpoint"

    async with written.issue("GET", url, {"timeout": 2.0}) as response:
        assert response.get_request_method() == "GET"
        assert response.get_request_url() == url
        assert response.get_request_options()["timeout"] == 2.0
        assert response.get_info("http_method") == "GET"
        assert response.get_info("url") == url


async def test_an_error_the_script_wrote_is_what_the_request_fails_with() -> None:
    written = MockResponse(b"", {"error": "ccc error"})

    with pytest.raises(TransportError, match="ccc error"):
        _ = written.issue("GET", URL, {})


async def test_a_response_no_client_issued_can_still_be_cancelled() -> None:
    written = MockResponse()

    await written.cancel()

    assert written.get_info("canceled") is True
    assert written.get_info("error") == "Response has been canceled."


async def test_cancelling_an_issued_response_says_so_and_closes_the_body() -> None:
    async with MockResponse(b"hello").issue("GET", URL, {}) as response:
        await response.cancel()

        assert response.get_info("canceled") is True
        with pytest.raises(TransportError, match=re.escape("Response has been canceled.")):
            _ = await response.get_content()


async def test_a_response_no_client_issued_is_not_an_answer_to_anything() -> None:
    written = MockResponse(b"hello")

    with pytest.raises(InvalidArgumentError, match="must be issued by MockHttpClient"):
        _ = await written.get_content()


async def test_leaving_the_block_of_a_response_no_client_issued_does_nothing() -> None:
    async with MockResponse(b"hello") as written:
        assert written.get_info("http_code") == 200


async def test_the_whole_record_is_readable_before_a_client_issues_the_response() -> None:
    written = MockResponse(b"hello", {"http_code": 201})

    assert written.get_info() == {"http_code": 201}
    assert written.get_info("nothing_of_the_sort") is None


async def test_the_content_length_says_what_the_body_really_is() -> None:
    written = MockResponse(b"abc=def", {"response_headers": ["Content-Length: 4"]})

    async with written.issue("POST", URL, {}) as response:
        assert response.get_header("content-length") == ["7"]
        assert response.get_info("response_headers") == [
            "HTTP/1.1 200 OK",
            "Content-Length: 7",
        ]


async def test_a_body_written_in_pieces_arrives_in_pieces_and_claims_no_length() -> None:
    async with MockResponse([b"hel", b"lo"]).issue("GET", URL, {}) as response:
        assert not response.has_header("content-length")
        assert await response.get_content() == b"hello"


async def test_the_status_line_and_the_headers_are_the_ones_the_script_wrote() -> None:
    written = MockResponse(b"", {"response_headers": ["HTTP/2 404 Nope", "X-Foo: bar"]})

    async with written.issue("GET", URL, {}) as response:
        assert response.get_status_code() == 404
        assert response.get_reason_phrase() == "Nope"
        assert response.get_protocol_version() == "2"
        assert response.get_header_line("x-foo") == "bar"
        assert response.has_header("X-FOO")
        assert response.get_headers()["X-Foo"] == ["bar"]


async def test_a_copy_carries_the_request_side_and_reads_the_one_body() -> None:
    written = MockResponse(b"hello")

    async with written.issue("GET", URL, {"user_data": "seven"}) as response:
        copy = response.with_header("X-Foo", "bar")

        assert isinstance(copy, MockResponse)
        assert copy.get_request_method() == "GET"
        assert copy.get_request_url() == URL
        assert copy.get_request_options() == response.get_request_options()
        assert copy.get_info("user_data") == "seven"
        assert copy.get_header("x-foo") == ["bar"]
        assert not response.has_header("x-foo")
        assert await copy.get_content() == b"hello"


async def test_every_copy_changes_the_one_thing_it_was_asked_to() -> None:
    written = MockResponse(b"", {"response_headers": {"X-Foo": "bar"}})

    async with written.issue("GET", URL, {}) as response:
        assert response.with_status(404, "Nope").get_status_code() == 404
        assert response.with_protocol_version("2").get_protocol_version() == "2"
        assert response.with_added_header("X-Foo", "ccc").get_header("x-foo") == ["bar", "ccc"]
        assert not response.without_header("X-Foo").has_header("x-foo")

        other = response.with_body(Stream.create(b"elsewhere"))
        assert await other.get_content() == b"elsewhere"


async def test_an_unsuccessful_status_is_raised_unless_the_caller_says_otherwise() -> None:
    written = MockResponse(b"gone", {"http_code": 404})

    async with written.issue("GET", URL, {}) as response:
        assert await response.get_content(throw=False) == b"gone"
        assert response.get_body().get_size() == 4
