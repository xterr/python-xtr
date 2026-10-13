from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import pytest
from xtr_http_message import Request
from xtr_service_contracts import ResetInterface

from xtr_http_client import MockHttpClient, MockResponse
from xtr_http_client.exception import InvalidArgumentError, TransportError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator

    from xtr_http_client_contracts import RequestOptions

    from xtr_http_client.mock_http_client import ResponseFactory, ScriptedFactory

pytestmark = pytest.mark.anyio

URL = "https://example.com"


def echoing(suffix: str = "") -> ScriptedFactory:
    """A script that answers with the request it was asked to answer."""

    def factory(method: str, url: str, options: RequestOptions) -> MockResponse:
        return MockResponse(f"{method}: {url} (body={options.get('body')}){suffix}")

    return factory


def answering_anything(_method: str, _url: str, _options: RequestOptions) -> MockResponse:
    return MockResponse()


def answering_with_a_list(_method: str, _url: str, _options: RequestOptions) -> list[MockResponse]:
    return [MockResponse()]


def answering_with_nothing(_method: str, _url: str, _options: RequestOptions) -> None:
    """A script that hands back nothing at all, which is not an answer."""


@pytest.mark.parametrize(
    ("factory", "answers"),
    [
        (
            echoing(),
            [
                b"POST: https://example.com/foo (body=payload)",
                b"POST: https://example.com/bar (body=payload)",
            ],
        ),
        (
            [echoing(" [1]"), echoing(" [2]")],
            [
                b"POST: https://example.com/foo (body=payload) [1]",
                b"POST: https://example.com/bar (body=payload) [2]",
            ],
        ),
        (
            [MockResponse(b"written out [1]"), MockResponse(b"written out [2]")],
            [b"written out [1]", b"written out [2]"],
        ),
        (
            iter([MockResponse(b"iterated [1]"), MockResponse(b"iterated [2]")]),
            [b"iterated [1]", b"iterated [2]"],
        ),
        (None, [b"", b""]),
    ],
    ids=["a callable", "callables", "responses", "an iterator", "nothing"],
)
async def test_every_shape_a_script_can_be_written_in_answers(
    factory: ResponseFactory | None,
    answers: list[bytes],
) -> None:
    client = MockHttpClient(factory)
    assert client.get_requests_count() == 0

    for url, expected in zip(["/foo", "/bar"], answers, strict=True):
        async with await client.request("POST", url, body="payload") as response:
            assert await response.get_content() == expected

    assert client.get_requests_count() == 2


async def test_one_written_answer_answers_every_request() -> None:
    client = MockHttpClient(MockResponse(b"the same again"))

    async with await client.request("GET", URL) as response:
        assert await response.get_content() == b"the same again"

    assert client.get_requests_count() == 1


async def test_a_script_that_has_to_be_awaited_is_awaited() -> None:
    async def factory(method: str, _url: str, _options: RequestOptions) -> MockResponse:
        return MockResponse(method.encode())

    client = MockHttpClient(factory)

    async with await client.request("DELETE", URL) as response:
        assert await response.get_content() == b"DELETE"


async def test_a_script_can_hold_a_callable_among_the_answers_written_out() -> None:
    client = MockHttpClient([MockResponse(b"written"), echoing()])

    async with await client.request("GET", "/first") as first:
        assert await first.get_content() == b"written"
    async with await client.request("GET", "/second") as second:
        assert await second.get_content() == b"GET: https://example.com/second (body=b'')"


@pytest.mark.parametrize(
    "factory",
    [
        answering_anything,
        MockResponse(),
        [MockResponse()],
        iter([MockResponse()]),
        None,
    ],
    ids=["a callable", "a response", "one response in a list", "an iterator", "nothing"],
)
async def test_a_script_of_any_shape_answers_a_request(factory: ResponseFactory | None) -> None:
    async with await MockHttpClient(factory).request("GET", "https://foo.bar") as response:
        assert response.get_status_code() == 200


async def test_a_script_written_as_a_generator_is_drawn_on_one_answer_at_a_time() -> None:
    def written() -> Iterator[MockResponse]:
        yield MockResponse(b"first")
        yield MockResponse(b"second")

    client = MockHttpClient(written())

    async with await client.request("GET", URL) as first:
        assert await first.get_content() == b"first"
    async with await client.request("GET", URL) as second:
        assert await second.get_content() == b"second"


@pytest.mark.parametrize(
    "factory",
    [
        [MockResponse(), MockResponse()],
        [echoing(), echoing()],
        iter([MockResponse(), MockResponse()]),
    ],
    ids=["responses", "callables", "an iterator"],
)
async def test_more_requests_than_answers_written_is_reported_as_the_mistake_it_is(
    factory: ResponseFactory,
) -> None:
    client = MockHttpClient(factory)

    async with await client.request("POST", "/foo"):
        pass
    async with await client.request("POST", "/foo"):
        pass

    with pytest.raises(
        TransportError,
        match=re.escape(
            "No more response left in the response factory iterator passed to "
            "MockHttpClient: the number of requests exceeds the number of responses."
        ),
    ):
        _ = await client.request("POST", "/foo")


async def test_a_script_with_nothing_in_it_says_so_rather_than_that_it_ran_out() -> None:
    client = MockHttpClient([])

    with pytest.raises(
        TransportError,
        match=re.escape("The response factory iterator passed to MockHttpClient is empty."),
    ):
        _ = await client.request("GET", URL)


@pytest.mark.parametrize(
    ("factory", "named"),
    [
        (answering_with_a_list, "list"),
        (answering_with_nothing, "null"),
        (iter(["ccc"]), "str"),
    ],
    ids=["a list", "nothing", "a string"],
)
async def test_a_script_offering_something_that_is_not_an_answer_is_refused(
    factory: object,
    named: str,
) -> None:
    client = MockHttpClient(cast("ResponseFactory", factory))

    with pytest.raises(
        TransportError,
        match=re.escape(
            "The response factory passed to MockHttpClient must return/yield an "
            f'instance of MockResponse, "{named}" given.'
        ),
    ):
        _ = await client.request("GET", "https://foo.bar")


async def test_a_status_of_zero_is_a_status_a_script_can_write() -> None:
    client = MockHttpClient(MockResponse(b"", {"response_headers": ["HTTP/1.1 000 "]}))

    async with await client.request("GET", "https://foo.bar") as response:
        assert response.get_status_code() == 0


async def test_the_moment_the_script_says_the_request_was_sent_is_the_one_recorded() -> None:
    client = MockHttpClient(MockResponse(b"foobarccc", {"start_time": 1701187598.313123}))

    async with await client.request("GET", URL) as response:
        assert response.get_info("start_time") == 1701187598.313123


async def test_a_relative_url_is_resolved_against_the_base_the_client_was_given() -> None:
    client = MockHttpClient(echoing(), "https://elsewhere.test/api/")

    async with await client.request("GET", "orders", query={"page": 2}) as response:
        assert response.get_request_url() == "https://elsewhere.test/api/orders?page=2"


async def test_a_relative_url_with_no_base_to_resolve_it_against_is_refused() -> None:
    client = MockHttpClient()

    with pytest.raises(InvalidArgumentError, match='Invalid URL "/foo": it is relative'):
        _ = await client.request("GET", "/foo", base_uri=None)


async def test_a_message_request_is_answered_as_a_method_and_a_url_are() -> None:
    client = MockHttpClient(echoing())

    async with await client.send_request(Request("PUT", "/orders/7")) as response:
        assert response.get_request_method() == "PUT"
        assert await response.get_content() == b"PUT: https://example.com/orders/7 (body=b'')"


async def test_the_options_the_request_was_made_with_are_the_merged_ones() -> None:
    client = MockHttpClient().with_options(timeout=2.0)

    async with await client.request("GET", URL, auth_bearer="token") as response:
        options = response.get_request_options()

        assert options["auth_bearer"] == "token"
        assert options["timeout"] == 2.0
        assert options["max_redirects"] == 20


async def test_an_option_no_client_knows_is_refused_before_anything_is_answered() -> None:
    client = MockHttpClient()
    # The typed signature makes a misspelled option, which is the subject here, unwritable.
    request = cast("Callable[..., Awaitable[object]]", client.request)

    with pytest.raises(InvalidArgumentError, match='Unsupported option "timoeut"'):
        _ = await request("GET", URL, timoeut=1)


async def test_a_method_no_server_would_read_as_one_is_refused() -> None:
    client = MockHttpClient()

    with pytest.raises(InvalidArgumentError, match="only uppercase letters are accepted"):
        _ = await client.request("Get", URL)


async def test_a_body_given_twice_over_is_refused() -> None:
    client = MockHttpClient()

    with pytest.raises(InvalidArgumentError, match='Define either the "json" or the "body"'):
        _ = await client.request("POST", URL, body=b"one", json={"two": True})


async def test_the_script_can_be_changed_without_unmaking_the_requests_already_made() -> None:
    client = MockHttpClient([MockResponse(b"first")])

    async with await client.request("GET", URL) as first:
        assert await first.get_content() == b"first"

    client.set_response_factory(MockResponse(b'{"foo": "bar"}'))

    async with await client.request("GET", URL) as second:
        assert await second.get_content() == b'{"foo": "bar"}'
    assert client.get_requests_count() == 2


async def test_the_count_of_requests_is_what_resetting_the_client_forgets() -> None:
    client = MockHttpClient(echoing())

    async with await client.request("POST", "/url", body="payload"):
        pass
    assert client.get_requests_count() == 1

    client.reset()

    assert client.get_requests_count() == 0
    assert isinstance(client, ResetInterface)


async def test_a_narrowed_client_answers_from_the_same_script() -> None:
    client = MockHttpClient(echoing())
    narrowed = client.with_options(base_uri="https://elsewhere.test")

    async with await narrowed.request("GET", "/orders") as response:
        assert response.get_request_url() == "https://elsewhere.test/orders"
    assert narrowed.get_requests_count() == 1
