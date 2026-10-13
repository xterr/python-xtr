from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import pytest
from xtr_http_message import Request

from xtr_http_client import MockHttpClient, MockResponse, ScopingHttpClient
from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.option_merge import as_options

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import HttpResponseInterface, RequestOptions

pytestmark = pytest.mark.anyio


def _inner() -> MockHttpClient:
    """A scripted client with no base URI, so only the scope resolves anything."""
    return MockHttpClient(None, None)


def _scopes(**by_regexp: Mapping[str, object]) -> dict[str, RequestOptions]:
    return {regexp: as_options(options) for regexp, options in by_regexp.items()}


def _scripted(response: HttpResponseInterface) -> MockResponse:
    """The scripted answer behind the interface, which knows what was asked of it."""
    assert isinstance(response, MockResponse)

    return response


async def test_a_relative_url_outside_every_scope_is_left_unresolved() -> None:
    client = ScopingHttpClient(_inner(), {})

    with pytest.raises(InvalidArgumentError):
        _ = await client.request("GET", "/foo")


async def test_a_relative_url_resolves_against_the_default_scope() -> None:
    client = ScopingHttpClient(
        _inner(),
        _scopes(**{".*": {"base_uri": "http://example.com", "query": {"a": "b"}}}),
        ".*",
    )

    async with _scripted(await client.request("GET", "/foo?f=g")) as response:
        assert response.get_request_url() == "http://example.com/foo?f=g&a=b"


async def test_the_first_matching_scope_is_the_one_that_applies() -> None:
    scopes = _scopes(**{".*/foo-bar": {"user_data": 1}, ".*": {"user_data": 2}})
    client = ScopingHttpClient(_inner(), scopes)

    async with _scripted(await client.request("GET", "http://example.com/foo-bar")) as response:
        assert response.get_request_options()["user_data"] == 1


@pytest.mark.parametrize("path", ["bar-foo", "foobar"])
async def test_a_url_no_narrow_scope_claims_falls_to_the_broad_one(path: str) -> None:
    scopes = _scopes(**{".*/foo-bar": {"user_data": 1}, ".*": {"user_data": 2}})
    client = ScopingHttpClient(_inner(), scopes)

    async with _scripted(await client.request("GET", f"http://example.com/{path}")) as response:
        assert response.get_request_options()["user_data"] == 2


async def test_a_scope_contributes_the_headers_the_request_left_out() -> None:
    scopes = _scopes(
        **{
            ".*/foo-bar": {"headers": {"X-FooBar": "unit-test-foo-bar"}},
            ".*": {"headers": {"Content-Type": "text/html"}},
        }
    )
    client = ScopingHttpClient(_inner(), scopes)

    async with _scripted(await client.request("GET", "http://example.com/foo-bar")) as response:
        assert response.get_request_options()["headers"] == {"X-FooBar": "unit-test-foo-bar"}


async def test_a_header_the_request_set_wins_over_the_scope_and_comes_first() -> None:
    scopes = _scopes(
        **{
            ".*/foo-bar": {"headers": {"X-FooBar": "unit-test-foo-bar"}},
            ".*": {"headers": {"Content-Type": "text/html", "X-FooBar": "scoped"}},
        }
    )
    client = ScopingHttpClient(_inner(), scopes)

    answer = await client.request(
        "GET",
        "http://example.com/bar-foo",
        headers={"X-FooBar": "unit-test"},
    )
    async with _scripted(answer) as response:
        headers = cast("Mapping[str, str]", response.get_request_options()["headers"])

        assert list(headers.items()) == [
            ("X-FooBar", "unit-test"),
            ("Content-Type", "text/html"),
        ]


async def test_an_option_the_request_named_wins_whole() -> None:
    client = ScopingHttpClient(_inner(), _scopes(**{".*": {"user_data": "scoped"}}))

    answer = await client.request("GET", "http://example.com/", user_data="asked for")
    async with _scripted(answer) as response:
        assert response.get_request_options()["user_data"] == "asked for"


async def test_for_base_uri_resolves_a_relative_url_against_it() -> None:
    client = ScopingHttpClient.for_base_uri(_inner(), "http://example.com/foo")

    async with _scripted(await client.request("GET", "/bar")) as response:
        assert response.get_request_url() == "http://example.com/bar"


async def test_for_base_uri_leaves_a_url_outside_the_scope_alone() -> None:
    client = ScopingHttpClient.for_base_uri(
        _inner(),
        "http://example.com/foo",
        as_options({"headers": {"X-Scoped": "yes"}}),
    )

    async with _scripted(await client.request("GET", "http://foo.bar/")) as response:
        assert response.get_request_url() == "http://foo.bar/"
        assert response.get_request_options()["headers"] == {}


async def test_for_base_uri_takes_a_regexp_of_its_own() -> None:
    client = ScopingHttpClient.for_base_uri(
        _inner(),
        "http://example.com/foo",
        as_options({"headers": {"X-Scoped": "yes"}}),
        r"http://(?:example|other)\.com/",
    )

    async with _scripted(await client.request("GET", "http://other.com/bar")) as response:
        assert response.get_request_options()["headers"] == {"X-Scoped": "yes"}


async def test_for_base_uris_resolves_against_the_first_one() -> None:
    client = ScopingHttpClient.for_base_uris(
        _inner(),
        ["http://a.example.com/foo", "http://b.example.com/"],
    )

    async with _scripted(await client.request("GET", "/bar")) as response:
        assert response.get_request_url() == "http://a.example.com/bar"


async def test_for_base_uris_resolves_against_the_base_uri_a_request_names() -> None:
    client = ScopingHttpClient.for_base_uris(
        _inner(),
        ["http://a.example.com/foo", "http://b.example.com/"],
    )

    answer = await client.request("GET", "/bar", base_uri="http://b.example.com/")
    async with _scripted(answer) as response:
        assert response.get_request_url() == "http://b.example.com/bar"


@pytest.mark.parametrize("base_uri", ["http://a.example.com/", "http://b.example.com/"])
async def test_for_base_uris_scopes_every_uri(base_uri: str) -> None:
    client = ScopingHttpClient.for_base_uris(
        _inner(),
        ["http://a.example.com/", "http://b.example.com/"],
        as_options({"headers": {"X-Scoped": "yes"}}),
    )

    async with _scripted(await client.request("GET", "/bar", base_uri=base_uri)) as response:
        assert response.get_request_options()["headers"] == {"X-Scoped": "yes"}


async def test_for_base_uris_leaves_an_unlisted_host_out_of_scope() -> None:
    client = ScopingHttpClient.for_base_uris(
        _inner(),
        ["http://a.example.com/", "http://b.example.com/"],
        as_options({"headers": {"X-Scoped": "yes"}}),
    )

    async with _scripted(await client.request("GET", "http://c.example.com/bar")) as response:
        assert response.get_request_options()["headers"] == {}


async def test_for_base_uris_refuses_an_empty_list() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match=re.escape("At least one base URI must be provided."),
    ):
        _ = ScopingHttpClient.for_base_uris(_inner(), [])


async def test_a_default_regexp_no_scope_is_mapped_to_is_refused() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match=re.escape('No options are mapped to the provided ".*" default regexp.'),
    ):
        _ = ScopingHttpClient(_inner(), {}, ".*")


async def test_send_request_takes_the_same_path_as_request() -> None:
    client = ScopingHttpClient.for_base_uri(
        _inner(),
        "http://example.com/foo",
        as_options({"headers": {"X-Scoped": "yes"}}),
    )

    async with _scripted(await client.send_request(Request("GET", "/bar"))) as response:
        assert response.get_request_url() == "http://example.com/bar"
        assert response.get_request_options()["headers"] == {"X-Scoped": "yes"}


async def test_with_options_wraps_a_narrowed_client_and_keeps_the_scopes() -> None:
    client = ScopingHttpClient.for_base_uri(_inner(), "http://example.com/foo")

    narrowed = client.with_options(auth_bearer="t0ken")

    async with _scripted(await narrowed.request("GET", "/bar")) as response:
        assert response.get_request_options()["auth_bearer"] == "t0ken"
        assert response.get_request_url() == "http://example.com/bar"

    async with _scripted(await client.request("GET", "/bar")) as original:
        assert original.get_request_options()["auth_bearer"] is None
