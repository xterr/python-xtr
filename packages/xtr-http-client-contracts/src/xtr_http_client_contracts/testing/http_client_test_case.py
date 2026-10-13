"""The conformance suite every client implementation runs against itself.

Subclass :class:`HttpClientTestCase`, return a client from ``create_client``, and the whole
suite runs against the fixture server. Nothing here is specific to one client: every assertion
is something the contract promises, so a client that passes is one a caller can hold through
the interface alone.

The suite is one class on purpose — it is the contract read as behaviour, and a reader checking
whether their client conforms reads it top to bottom. Splitting it by topic would only move the
reading around. (allow: SIZE_OK — one conformance suite, one file.)

What came from the reference suite, test by test. "ported" means the same calls and the same
assertions; "translated" says what had to change for an async client whose ``request()``
returns once the status line and the headers are in.

==================================  ==========================================================
``testGetRequest``                  translated: eager request
``testHeadRequest``                 translated: eager request
``testNonBufferedGetRequest``       ported
``testBufferSink``                  no counterpart: the sink is a writable stream resource,
                                    which an async client has no equivalent of
``testConditionalBuffering``        translated: the callback is handed the response, and reads
                                    the headers off it
``testReentrantBufferCallback``     translated: async callback receiving the response
``testThrowingBufferCallback``      translated: what the callback raises comes back from
                                    ``request()``
``testUnsupportedOption``           translated: an unsupported option is a ``TransportError``
``testHttpVersion``                 translated: ``http_version`` is the version as text
``testChunkedEncoding``             translated: the fixture's chunked body
``testClientError``                 translated: the first pair of the stream starts the run
``testIgnoreErrors``                ported
``testDnsError``                    translated: eager request
``testInlineAuth``                  translated: the fixture's ``AUTH_USER`` / ``AUTH_PW``
``testBadRequestBody``              translated: eager request
``test304``                         ported
``testRedirects``                   translated: parametrized, and the header filter names
                                    ``Content-Type`` because the fixture declares a length
``testInvalidRedirect``             translated: the status is raised by reading the content
``testRelativeRedirects``           ported
``testRedirect307``                 ported
``testMaxRedirects``                translated: the status is raised by reading the content
``testStream``                      translated: ``async for``
``testAddToStream``                 translated: ``async for``
``testCompleteTypeError``           ported
``testOnProgress``                  ported
``testPostJson``                    ported
``testPostArray``                   ported
``testPostResource``                translated: an ``AsyncIterable[bytes]`` body
``testPostCallback``                translated: an ``AsyncIterable[bytes]`` body
``testCancel``                      ported
``testInfoOnCanceledResponse``      ported
``testCancelInStream``              translated: ``async for``
``testOnProgressCancel``            ported
``testOnProgressError``             translated: a ``BaseException`` that is not an
                                    ``Exception`` stands for a bug, which is never wrapped
``testResolve``                     translated: eager request
``testIdnResolve``                  ported
``testIPv6Resolve``                 translated: a second server, started by the test
``testNotATimeout``                 ported
``testTimeoutOnAccess``             translated: eager request
``testTimeoutIsNotAFatalError``     ported
``testTimeoutOnStream``             translated: ``async for``
``testUncheckedTimeoutThrows``      translated: the ``async with`` exit raises the timeout
                                    nobody asked the chunk about
``testTimeoutWithActiveConcurrentStream``  translated: two servers, started by the test
``testTimeoutOnInitialize``         translated: eager request
``testTimeoutOnDestruct``           translated: eager request — the timeouts are reported
                                    where the requests are made, not where they are released
``testDestruct``                    translated: the ``async with`` exit frees the transfer
``testGetContentAfterDestruct``     translated: the ``async with`` exit raises the status
``testGetEncodedContentAfterDestruct``  translated: the ``async with`` exit raises the status
``testProxy``                       translated: the environment is patched, not written to
``testNoProxy``                     translated: the environment is patched, not written to
``testAutoEncodingRequest``         ported
``testBaseUri``                     ported
``testQuery``                       ported
``testInformationalResponse``       ported
``testInformationalResponseStream`` translated: ``async for``, and header names are compared
                                    lowercased because the message contract keeps their case
``testUserlandEncodingRequest``     ported
``testGzipBroken``                  ported
``testMaxDuration``                 ported
``testMaxConnectDurationInfo``      ported
``testMaxConnectDuration``          translated: eager request
``testWithOptions``                 ported
``testBindToPort``                  ported
``testBindToPortV6``                translated: a second server, started by the test
==================================  ==========================================================

63 reference methods: 62 here, 1 with no counterpart. One test is the contract's own addition,
with nothing behind it in the reference suite: ``test_body_stream``, which reads the body
through the message's stream rather than in one go.
"""

from __future__ import annotations

import gzip
import json
import re
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, ClassVar, Protocol, TypeVar, cast

import anyio
import pytest

from xtr_http_client_contracts.exception import (
    ClientError,
    RedirectionError,
    TransportError,
    TransportTimeoutError,
)

from .test_http_server import TestHttpServer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator, Sequence

    from xtr_http_client_contracts.chunk_interface import ChunkInterface
    from xtr_http_client_contracts.http_client_interface import HttpClientInterface
    from xtr_http_client_contracts.request_options import RequestOptions
    from xtr_http_client_contracts.response_interface import ResponseInterface
    from xtr_http_client_contracts.response_stream_interface import ResponseStreamInterface

__all__ = ["HttpClientTestCase"]

_T = TypeVar("_T")

_HOST = "localhost"
_PORT = 8057
_BASE_URI = f"http://{_HOST}:{_PORT}"

# The servers a handful of tests start for themselves, because what they provoke is one
# transfer holding up another, which needs somewhere else to be answered from.
_SECOND_PORT = 8067
_THIRD_PORT = 8077
_IPV6_HOST = "::1"
_IPV6_PORT = 8087

# A name reserved for documentation, pinned to the fixture server by the `resolve` option.
_PINNED_HOST = "pinned.example"

# The hops of a redirect chain, as the reference suite reads them out of `response_headers`:
# the status lines, where each hop pointed, and what each hop answered with. The fixture's
# echo routes declare a length, so the filter names `Content-Type` rather than any `Cont`
# header.
_CHAIN_FIELDS = ("HTTP", "Location:", "Content-Type:")

_PROXIED_URI = re.compile(r"^http://(localhost|127\.0\.0\.1):8057/$")


class _NamedNode(Protocol):
    """The collected test, as much of it as the skip list needs."""

    name: str


class _RunningTest(Protocol):
    """What the runner tells a fixture about the test it is running for.

    The runner leaves this untyped, and the suite will not loosen its own checking to read
    one string: this says what is actually there and nothing else.
    """

    @property
    def node(self) -> _NamedNode: ...


class _ProgressBug(BaseException):
    """A bug raised from a progress callback, which a client must never wrap.

    Not an :class:`Exception`: the contract has a client turn a failing progress callback into
    a :class:`TransportError`, and this is how the suite says "that is for errors the caller
    meant, not for a mistake in their own code".
    """


def _decode_object(content: bytes) -> Mapping[str, object]:
    """``content`` read as the JSON object it is.

    The standard library's decoder answers anything at all; saying here what the suite asks of
    it keeps that looseness to one place.
    """
    return cast("Mapping[str, object]", cast("object", json.loads(content)))


def _expect(value: object, kind: type[_T]) -> _T:
    """``value``, once it is a ``kind``; the transfer info comes out of the contract untyped."""
    if not isinstance(value, kind):
        raise TypeError(f"expected {kind.__name__}, got {value!r}")
    return value


def _info(response: ResponseInterface, key: str, kind: type[_T]) -> _T:
    """The ``key`` entry of ``response``'s info, narrowed to ``kind``."""
    return _expect(response.get_info(key), kind)


def _info_map(response: ResponseInterface) -> Mapping[str, object]:
    """Every entry of ``response``'s info at once."""
    return cast("Mapping[str, object]", _expect(response.get_info(), Mapping))


def _info_lines(response: ResponseInterface) -> list[str]:
    """The ``response_headers`` entry, as the lines it holds."""
    lines = cast("Sequence[object]", response.get_info("response_headers"))
    return [_expect(line, str) for line in lines]


def _chain(response: ResponseInterface) -> list[str]:
    """Where every hop of a redirect chain went, and what it answered with."""
    return [line for line in _info_lines(response) if line.startswith(_CHAIN_FIELDS)]


def _header(response: ResponseInterface, name: str) -> Sequence[str]:
    """Every value under ``name``, matched without regard to case."""
    wanted = name.lower()
    headers = response.get_headers()
    for key, values in headers.items():
        if key.lower() == wanted:
            return values
    raise AssertionError(f"no {name} header among {sorted(headers)}")


def _header_names(response: ResponseInterface) -> list[str]:
    """The header names, lowercased: the contract keeps the case they arrived in."""
    return [name.lower() for name in response.get_headers()]


async def _first_pair(
    stream: ResponseStreamInterface,
) -> tuple[ResponseInterface, ChunkInterface]:
    """The first pair ``stream`` yields, which is what gets its transfers going."""
    async for pair in stream:
        return pair
    raise AssertionError("the stream ended without yielding a chunk")


async def _parts(*parts: bytes) -> AsyncIterator[bytes]:
    """``parts`` as a body produced piece by piece."""
    for part in parts:
        yield part


async def _not_bytes() -> AsyncIterator[bytes]:
    """A body yielding something that is not bytes, which no client can send."""
    yield cast("bytes", cast("object", []))


class HttpClientTestCase:
    """What every client that satisfies the contract does, run against the fixture server.

    Subclass it and return the client under test::

        class TestMyClient(HttpClientTestCase):
            def create_client(self) -> HttpClientInterface:
                return MyClient()

    A client that cannot honour part of the contract yet names the tests it skips and why::

        class TestMyClient(HttpClientTestCase):
            skipped_tests: ClassVar[Mapping[str, str]] = {
                "test_bind_to_port_v6": "no IPv6 in this environment",
            }

    The suite starts the fixture server once for the whole session; the few tests that need a
    second one start and stop it themselves.
    """

    __test__: ClassVar[bool] = False  # the suite is a base class, not a test case of its own

    pytestmark: ClassVar[pytest.MarkDecorator] = pytest.mark.anyio

    skipped_tests: ClassVar[Mapping[str, str]] = {}
    """Test names to skip, mapped to why. A parametrized test is named without its parameter."""

    @pytest.fixture(scope="session", autouse=True)
    @staticmethod
    def fixture_server() -> Iterator[TestHttpServer]:
        """The server every test points at, listening for the whole session."""
        with TestHttpServer(port=_PORT) as server:
            yield server

    @pytest.fixture(autouse=True)
    def _skip_if_unsupported(self, request: pytest.FixtureRequest) -> None:
        """Skip a test this client has declared it does not satisfy."""
        running = cast("_RunningTest", cast("object", request))
        reason = self.skipped_tests.get(running.node.name.partition("[")[0])
        if reason is not None:
            pytest.skip(reason)

    def create_client(self) -> HttpClientInterface:
        """Return the client the suite is to run against.

        Returns:
            A client, freshly made: a test may cancel transfers or exhaust a connection pool,
            so no two tests share one.
        """
        raise NotImplementedError("a subclass returns the client under test")

    async def test_get_request(self) -> None:
        """A plain GET: the status and headers are in, and the body decodes to what was sent."""
        client = self.create_client()
        data = object()
        response = await client.request(
            "GET",
            _BASE_URI,
            headers={"Foo": "baR"},
            user_data=data,
        )

        assert _info_lines(response)
        assert _info_map(response)["user_data"] is data
        assert response.get_status_code() == 200

        info = _info_map(response)
        assert info["error"] is None
        assert info["redirect_count"] == 0
        assert _info_lines(response)[0] == "HTTP/1.1 200 OK"
        assert info["url"] == f"{_BASE_URI}/"

        assert _header(response, "content-type") == ["application/json"]

        body = _decode_object(await response.get_content())
        assert body == await response.to_array()

        assert body["SERVER_PROTOCOL"] == "HTTP/1.1"
        assert body["REQUEST_URI"] == "/"
        assert body["REQUEST_METHOD"] == "GET"
        assert body["HTTP_HOST"] == f"{_HOST}:{_PORT}"
        assert body["HTTP_FOO"] == "baR"

        broken = await client.request("GET", f"{_BASE_URI}/length-broken")

        with pytest.raises(TransportError):
            _ = await broken.get_content()

    async def test_body_stream(self) -> None:
        """The body is also the message's stream, which reads the same bytes.

        Nothing in the reference suite reads a response that way — it has no streamed body
        on the message — so this is the contract's own addition.
        """
        client = self.create_client()
        response = await client.request("GET", _BASE_URI, headers={"Foo": "baR"})

        content = await response.get_content()
        body = response.get_body()

        assert await body.get_contents() == content
        await body.rewind()
        assert await body.read(len(content)) == content

    async def test_head_request(self) -> None:
        """A HEAD answers headers describing a body it does not send."""
        client = self.create_client()
        response = await client.request(
            "HEAD",
            f"{_BASE_URI}/head",
            headers={"Foo": "baR"},
            buffer=False,
        )

        assert _info_lines(response)
        assert response.get_status_code() == 200
        assert _info_lines(response)[0] == "HTTP/1.1 200 OK"

        assert _header(response, "content-type") == ["application/json"]
        assert int(_header(response, "content-length")[0]) > 0

        assert await response.get_content() == b""

    async def test_non_buffered_get_request(self) -> None:
        """With buffering off, the body is readable once and once only."""
        client = self.create_client()
        response = await client.request("GET", _BASE_URI, buffer=False, headers={"Foo": "baR"})

        body = await response.to_array()
        assert body["HTTP_FOO"] == "baR"

        with pytest.raises(TransportError):
            _ = await response.get_content()

    async def test_conditional_buffering(self) -> None:
        """Buffering kept means the same bytes twice; refused by the callback means once."""
        client = self.create_client()
        response = await client.request("GET", _BASE_URI)
        first_content = await response.get_content()
        second_content = await response.get_content()

        assert first_content == second_content

        def refuse(response: ResponseInterface) -> bool:
            """Refuse to buffer, having read the headers the decision is made from."""
            assert _header(response, "content-type") == ["application/json"]
            return False

        response = await client.request("GET", _BASE_URI, buffer=refuse)
        _ = await response.get_content()

        with pytest.raises(TransportError):
            _ = await response.get_content()

    async def test_reentrant_buffer_callback(self) -> None:
        """A buffer callback may cancel the response it is handed, leaving nothing to read."""
        client = self.create_client()

        async def buffer(response: ResponseInterface) -> bool:
            await response.cancel()
            return True

        response = await client.request("GET", _BASE_URI, buffer=buffer)

        assert response.get_status_code() == 200

        with pytest.raises(TransportError):
            _ = await response.get_content()

    async def test_throwing_buffer_callback(self) -> None:
        """A buffer callback that raises fails the request, saying what it raised."""
        client = self.create_client()

        def buffer(response: ResponseInterface) -> bool:
            del response
            raise RuntimeError("Boo.")

        with pytest.raises(TransportError, match="Boo"):
            _ = await client.request("GET", _BASE_URI, buffer=buffer)

    async def test_unsupported_option(self) -> None:
        """An option the client has never heard of is refused, never quietly obeyed."""
        client = self.create_client()
        unknown = cast("RequestOptions", cast("object", {"capture_peer_cert": 1.0}))

        with pytest.raises(TransportError):
            _ = await client.request("GET", _BASE_URI, **unknown)

    async def test_http_version(self) -> None:
        """Asking for HTTP/1.0 sends HTTP/1.0, which the echo answers with."""
        client = self.create_client()
        response = await client.request("GET", _BASE_URI, http_version="1.0")

        assert response.get_status_code() == 200
        assert _info_lines(response)[0] == "HTTP/1.0 200 OK"

        body = await response.to_array()

        assert body["SERVER_PROTOCOL"] == "HTTP/1.0"
        assert body["REQUEST_METHOD"] == "GET"
        assert body["REQUEST_URI"] == "/"

    async def test_chunked_encoding(self) -> None:
        """A chunked body is reassembled; framing that stops mid-chunk fails the transfer."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/chunked")

        assert _header(response, "transfer-encoding") == ["chunked"]
        assert await response.get_content() == b"chunked data works!"

        response = await client.request("GET", f"{_BASE_URI}/chunked-broken")

        with pytest.raises(TransportError):
            _ = await response.get_content()

    async def test_client_error(self) -> None:
        """A 404 is an answer: told about when asked for, readable when not."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/404")

        _ = await _first_pair(client.stream(response))

        assert _info(response, "http_code", int) == 404

        with pytest.raises(ClientError):
            _ = await response.get_content()

        assert response.get_status_code() == 404
        assert _header(response, "content-type") == ["application/json"]
        assert await response.get_content(throw=False)

        response = await client.request("GET", f"{_BASE_URI}/404")

        with pytest.raises(ClientError):
            async for _paired, chunk in client.stream(response):
                assert chunk.is_first()

    async def test_ignore_errors(self) -> None:
        """Reading the status of a 404 is not being told about it."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/404")

        assert response.get_status_code() == 404

    async def test_dns_error(self) -> None:
        """A host that will not resolve fails the request, and fails it again on a retry."""
        client = self.create_client()

        with pytest.raises(TransportError):
            _ = await client.request("GET", f"{_BASE_URI}/301/bad-tld")

        with pytest.raises(TransportError):
            _ = await client.request("GET", f"{_BASE_URI}/301/bad-tld")

    async def test_inline_auth(self) -> None:
        """Credentials in the URL are sent as basic credentials, decoded as given."""
        client = self.create_client()
        response = await client.request("GET", f"http://foo:bar%3Dbar@{_HOST}:{_PORT}")

        body = await response.to_array()

        assert body["AUTH_USER"] == "foo"
        assert body["AUTH_PW"] == "bar=bar"

    async def test_bad_request_body(self) -> None:
        """A body producing something that is not bytes fails the request."""
        client = self.create_client()

        with pytest.raises(TransportError):
            _ = await client.request("POST", f"{_BASE_URI}/", body=_not_bytes())

    async def test_304(self) -> None:
        """A 304 carries no body, whatever length it declares."""
        client = self.create_client()
        response = await client.request(
            "GET",
            f"{_BASE_URI}/304",
            headers={"If-Match": '"abc"'},
            buffer=False,
        )

        assert response.get_status_code() == 304
        assert await response.get_content(throw=False) == b""

    @pytest.mark.parametrize("headers", [[], ["Content-Length: 7"]])
    async def test_redirects(self, headers: list[str]) -> None:
        """A chain is followed as GET, and credentials come back when it returns home."""
        client = self.create_client()
        response = await client.request(
            "POST",
            f"{_BASE_URI}/301",
            auth_basic="foo:bar",
            headers=headers,
            body=_parts(b"foo=bar"),
        )

        body = await response.to_array()
        assert body["REQUEST_METHOD"] == "GET"
        assert body["HTTP_AUTHORIZATION"] == "Basic Zm9vOmJhcg=="
        assert _info(response, "url", str) == f"{_BASE_URI}/"

        assert _info(response, "redirect_count", int) == 2
        assert response.get_info("redirect_url") is None

        assert _chain(response) == [
            "HTTP/1.1 301 Moved Permanently",
            "Location: http://127.0.0.1:8057/302",
            "Content-Type: application/json",
            "HTTP/1.1 302 Found",
            f"Location: {_BASE_URI}/",
            "Content-Type: application/json",
            "HTTP/1.1 200 OK",
            "Content-Type: application/json",
        ]

    async def test_invalid_redirect(self) -> None:
        """A Location nothing can be made of is left as the 3xx it came on."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/301/invalid")

        assert response.get_status_code() == 301
        assert _header(response, "location") == ["//?foo=bar"]
        assert _info(response, "redirect_count", int) == 0
        assert response.get_info("redirect_url") is None

        with pytest.raises(RedirectionError):
            _ = await response.get_content()

    async def test_relative_redirects(self) -> None:
        """A relative Location is resolved; following none leaves it to be read."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/302/relative")

        body = await response.to_array()

        assert body["REQUEST_URI"] == "/"
        assert response.get_info("redirect_url") is None

        response = await client.request("GET", f"{_BASE_URI}/302/relative", max_redirects=0)

        assert response.get_status_code() == 302
        assert _info(response, "redirect_url", str) == f"{_BASE_URI}/"

    async def test_redirect_307(self) -> None:
        """A 307 keeps the method and the body, once it is followed."""
        client = self.create_client()

        response = await client.request(
            "POST",
            f"{_BASE_URI}/307",
            body=_parts(b"foo=bar"),
            max_redirects=0,
        )

        assert response.get_status_code() == 307

        response = await client.request("POST", f"{_BASE_URI}/307", body="foo=bar")

        assert await response.to_array() == {"foo": "bar", "REQUEST_METHOD": "POST"}

    async def test_max_redirects(self) -> None:
        """One hop too few ends on the 3xx, saying where it would have gone."""
        client = self.create_client()
        response = await client.request(
            "GET",
            f"{_BASE_URI}/301",
            max_redirects=1,
            auth_basic="foo:bar",
        )

        with pytest.raises(RedirectionError):
            _ = await response.get_content()

        assert response.get_status_code() == 302
        assert _info(response, "redirect_count", int) == 1
        assert _info(response, "redirect_url", str) == f"{_BASE_URI}/"

        assert _chain(response) == [
            "HTTP/1.1 301 Moved Permanently",
            "Location: http://127.0.0.1:8057/302",
            "Content-Type: application/json",
            "HTTP/1.1 302 Found",
            f"Location: {_BASE_URI}/",
            "Content-Type: application/json",
        ]

    async def test_stream(self) -> None:
        """A run opens with the head and ends with the last chunk, and says so again after."""
        client = self.create_client()

        response = await client.request("GET", _BASE_URI)
        paired: ResponseInterface | None = None
        result: list[str] = []

        # B007 is suppressed because `paired` is what the assertion after the loop is about.
        async for paired, chunk in client.stream(response):  # noqa: B007
            if chunk.is_timeout():
                result.append("t")
            elif chunk.is_last():
                result.append("l")
            elif chunk.is_first():
                result.append("f")

        assert paired is response
        assert result == ["f", "l"]

        last: ChunkInterface | None = None
        seen = 0

        # B007 is suppressed because `last` is what the assertion after the loop is about.
        async for _paired, last in client.stream(response):  # noqa: B007
            seen += 1

        assert seen == 1
        assert last is not None
        assert last.is_last()

    async def test_add_to_stream(self) -> None:
        """A response made while a run is going on is read in a run of its own."""
        client = self.create_client()

        first = await client.request("GET", _BASE_URI)

        completed: list[ResponseInterface] = []
        second: ResponseInterface | None = None
        pool: list[ResponseInterface] = [first]

        while pool:
            chunks = client.stream(pool)
            pool = []

            async for paired, chunk in chunks:
                if not chunk.is_last():
                    continue

                if paired is first:
                    second = await client.request("GET", _BASE_URI)
                    pool.append(second)

                completed.append(paired)

        assert completed == [first, second]

    async def test_complete_type_error(self) -> None:
        """Streaming something that is not a response is a mistake, not a transfer failure."""
        client = self.create_client()
        not_a_response = cast("ResponseInterface", cast("object", 123))

        with pytest.raises(TypeError):
            _ = await _first_pair(client.stream(not_a_response))

    async def test_on_progress(self) -> None:
        """The progress callback is told the totals and where the transfer is going."""
        client = self.create_client()
        steps: list[tuple[int, int, Mapping[str, object]]] = []

        def on_progress(received: int, total: int, info: Mapping[str, object]) -> None:
            steps.append((received, total, dict(info)))

        response = await client.request(
            "POST",
            f"{_BASE_URI}/post",
            headers={"Content-Length": "14"},
            body="foo=0123456789",
            on_progress=on_progress,
        )

        body = await response.to_array()

        assert body == {"foo": "0123456789", "REQUEST_METHOD": "POST"}
        assert steps[0][:2] == (0, 0)
        assert steps[-1][:2] == (57, 57)
        assert steps[0][2]["url"] == f"{_BASE_URI}/post"

    async def test_post_json(self) -> None:
        """A JSON body is sent as JSON, and says so in its content type."""
        client = self.create_client()

        response = await client.request("POST", f"{_BASE_URI}/post", json={"foo": "bar"})

        body = dict(await response.to_array())

        assert "json" in _expect(body.pop("content-type"), str)
        assert body == {"foo": "bar", "REQUEST_METHOD": "POST"}

    async def test_post_array(self) -> None:
        """A mapping body is sent as a form, which the echo answers field by field."""
        client = self.create_client()

        response = await client.request("POST", f"{_BASE_URI}/post", body={"foo": "bar"})

        assert await response.to_array() == {"foo": "bar", "REQUEST_METHOD": "POST"}

    async def test_post_resource(self) -> None:
        """A body read from somewhere else is sent as it is produced."""
        client = self.create_client()

        response = await client.request(
            "POST",
            f"{_BASE_URI}/post",
            body=_parts(b"foo=0123456789"),
        )

        body = await response.to_array()

        assert body == {"foo": "0123456789", "REQUEST_METHOD": "POST"}

    async def test_post_callback(self) -> None:
        """A body produced in pieces, empty ones included, arrives as one form."""
        client = self.create_client()

        response = await client.request(
            "POST",
            f"{_BASE_URI}/post",
            body=_parts(b"foo", b"", b"=", b"0123456789"),
        )

        assert await response.to_array() == {"foo": "0123456789", "REQUEST_METHOD": "POST"}

    async def test_cancel(self) -> None:
        """A cancelled transfer has nothing left to read."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/timeout-header")

        await response.cancel()

        with pytest.raises(TransportError):
            _ = await response.get_content()

    async def test_info_on_canceled_response(self) -> None:
        """Cancelling is something the transfer info records."""
        client = self.create_client()

        response = await client.request("GET", f"{_BASE_URI}/timeout-header")

        assert _info(response, "canceled", bool) is False
        await response.cancel()
        assert _info(response, "canceled", bool) is True

    async def test_cancel_in_stream(self) -> None:
        """A response cancelled mid-run cannot be streamed again."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/404")

        async for _paired, _chunk in client.stream(response):
            await response.cancel()

        with pytest.raises(TransportError):
            async for _paired, _chunk in client.stream(response):
                pass

    async def test_on_progress_cancel(self) -> None:
        """A progress callback that raises aborts the transfer, keeping what it raised."""
        client = self.create_client()

        def on_progress(received: int, total: int, info: Mapping[str, object]) -> None:
            del total, info
            if received > 0:
                raise RuntimeError("Aborting the request.")

        response = await client.request(
            "GET",
            f"{_BASE_URI}/timeout-body",
            on_progress=on_progress,
        )

        with pytest.raises(TransportError) as caught:
            async for _paired, _chunk in client.stream([response]):
                pass

        assert str(caught.value.__cause__) == "Aborting the request."

        assert response.get_info("error") is not None

        with pytest.raises(TransportError):
            _ = await response.get_content()

    async def test_on_progress_error(self) -> None:
        """A bug in a progress callback reaches the caller as the bug it is."""
        client = self.create_client()

        def on_progress(received: int, total: int, info: Mapping[str, object]) -> None:
            del total, info
            if received > 0:
                raise _ProgressBug("BUG.")

        response = await client.request(
            "GET",
            f"{_BASE_URI}/timeout-body",
            on_progress=on_progress,
        )

        with pytest.raises(_ProgressBug, match=r"BUG\."):
            async for _paired, _chunk in client.stream([response]):
                pass

        assert response.get_info("error") is not None

        with pytest.raises(TransportError):
            _ = await response.get_content()

    async def test_resolve(self) -> None:
        """A host pinned to an address is reached at it, and is not once the pin is gone."""
        client = self.create_client()
        response = await client.request(
            "GET",
            f"http://{_PINNED_HOST}:{_PORT}/",
            resolve={_PINNED_HOST: "127.0.0.1"},
        )

        assert response.get_status_code() == 200
        assert (
            await client.request("GET", f"http://{_PINNED_HOST}:{_PORT}/")
        ).get_status_code() == 200

        with pytest.raises(TransportError):
            _ = await client.request("GET", f"http://{_PINNED_HOST}:{_PORT}/", timeout=1)

    async def test_idn_resolve(self) -> None:
        """A very long label and a non-ASCII name both resolve to what they are pinned to."""
        client = self.create_client()

        long_host = "0" + "-" * 61 + "0.com"
        response = await client.request(
            "GET",
            f"http://{long_host}:{_PORT}/",
            resolve={long_host: "127.0.0.1"},
        )

        assert response.get_status_code() == 200

        response = await client.request(
            "GET",
            f"http://Bücher.example:{_PORT}/",
            resolve={"xn--bcher-kva.example": "127.0.0.1"},
        )

        assert response.get_status_code() == 200

    async def test_ipv6_resolve(self) -> None:
        """A host pinned to an IPv6 address is reached over IPv6."""
        server = TestHttpServer(host=_IPV6_HOST, port=_IPV6_PORT)
        server.start()
        try:
            client = self.create_client()
            response = await client.request(
                "GET",
                f"http://{_PINNED_HOST}:{_IPV6_PORT}/",
                resolve={_PINNED_HOST: _IPV6_HOST},
            )

            assert response.get_status_code() == 200
        finally:
            server.stop()

    async def test_not_a_timeout(self) -> None:
        """The timeout is how long a transfer may go quiet for, not how long it may take."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/timeout-header", timeout=0.9)
        await anyio.sleep(1)
        assert response.get_status_code() == 200

    async def test_timeout_on_access(self) -> None:
        """A head that does not arrive in time fails the request."""
        client = self.create_client()

        with pytest.raises(TransportError):
            _ = await client.request("GET", f"{_BASE_URI}/timeout-header", timeout=0.1)

    async def test_timeout_is_not_a_fatal_error(self) -> None:
        """A transfer that timed out mid-body carries on being read."""
        await anyio.sleep(0.3)  # let the previous test release the server
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/timeout-body", timeout=0.25)

        with pytest.raises(TransportTimeoutError):
            _ = await response.get_content()

        for _attempt in range(10):
            try:
                content = await response.get_content()
            except TransportTimeoutError:
                continue
            assert content == b"<1><2>"
            break
        else:
            pytest.fail("the body never arrived")

    async def test_timeout_on_stream(self) -> None:
        """A run says it went quiet, and picks the body up where it left off."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/timeout-body")

        assert response.get_status_code() == 200

        result: list[bytes] = []

        async for _paired, chunk in client.stream([response], 0.2):
            result.append(b"t" if chunk.is_timeout() else chunk.get_content())

        assert result == [b"<1>", b"t"]

        async for paired, chunk in client.stream([response]):
            assert chunk.get_content() == b"<2>"
            assert await paired.get_content() == b"<1><2>"
            return

        pytest.fail("the response should have completed")

    async def test_unchecked_timeout_throws(self) -> None:
        """A run that went quiet and was never asked about says so on the way out."""
        client = self.create_client()

        with pytest.raises(TransportError):
            async with await client.request("GET", f"{_BASE_URI}/timeout-body") as response:
                async for _paired, _chunk in client.stream([response], 0.1):
                    pass

    async def test_timeout_with_active_concurrent_stream(self) -> None:
        """A transfer that keeps arriving does not hold a timeout back."""
        first = TestHttpServer(port=_SECOND_PORT)
        second = TestHttpServer(port=_THIRD_PORT)
        first.start()
        second.start()
        try:
            client = self.create_client()
            streaming = await client.request("GET", f"http://{_HOST}:{_SECOND_PORT}/max-duration")
            blocking = await client.request(
                "GET",
                f"http://{_HOST}:{_THIRD_PORT}/timeout-body",
                timeout=0.25,
            )

            assert streaming.get_status_code() == 200
            assert blocking.get_status_code() == 200

            with pytest.raises(TransportError):
                _ = await blocking.get_content()
        finally:
            first.stop()
            second.stop()

    async def test_timeout_on_initialize(self) -> None:
        """Four heads that never arrive time out alongside each other, not one after another."""
        first = TestHttpServer(port=_SECOND_PORT)
        second = TestHttpServer(port=_THIRD_PORT)
        first.start()
        second.start()
        try:
            client = self.create_client()
            start = time.monotonic()

            async with anyio.create_task_group() as requests:
                for port in (_SECOND_PORT, _THIRD_PORT, _SECOND_PORT, _THIRD_PORT):
                    _ = requests.start_soon(self._expect_timeout, client, port)

            assert time.monotonic() - start < 1.0
        finally:
            first.stop()
            second.stop()

    async def test_timeout_on_destruct(self) -> None:
        """The same four, each reported where its request was made."""
        first = TestHttpServer(port=_SECOND_PORT)
        second = TestHttpServer(port=_THIRD_PORT)
        first.start()
        second.start()
        try:
            client = self.create_client()
            start = time.monotonic()

            for port in (_SECOND_PORT, _THIRD_PORT, _SECOND_PORT, _THIRD_PORT):
                with pytest.raises(TransportError):
                    _ = await client.request(
                        "GET",
                        f"http://{_HOST}:{port}/timeout-header",
                        timeout=0.25,
                    )

            assert time.monotonic() - start < 2.0
        finally:
            first.stop()
            second.stop()

    async def test_destruct(self) -> None:
        """Leaving the block frees a transfer rather than waiting for the rest of it."""
        client = self.create_client()

        start = time.monotonic()
        async with await client.request("GET", f"{_BASE_URI}/timeout-long"):
            pass
        duration = time.monotonic() - start

        assert duration > 1
        assert duration < 4

    async def test_get_content_after_destruct(self) -> None:
        """A status nobody looked at is raised on the way out, carrying its response."""
        client = self.create_client()

        with pytest.raises(ClientError) as caught:
            async with await client.request("GET", f"{_BASE_URI}/404"):
                pass

        body = await caught.value.response.to_array(throw=False)
        assert body["REQUEST_METHOD"] == "GET"

    async def test_get_encoded_content_after_destruct(self) -> None:
        """The response it carries has its body decoded, however late the body arrived."""
        client = self.create_client()

        with pytest.raises(ClientError) as caught:
            async with await client.request("GET", f"{_BASE_URI}/404-gzipped"):
                pass

        assert await caught.value.response.get_content(throw=False) == b"some text"

    async def test_proxy(self) -> None:
        """A proxy is asked for the absolute URL, with its own credentials, redirects too."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/", proxy=_BASE_URI)

        body = await response.to_array()
        assert body["HTTP_HOST"] == f"{_HOST}:{_PORT}"
        assert _PROXIED_URI.match(_expect(body["REQUEST_URI"], str))

        response = await client.request(
            "GET",
            f"{_BASE_URI}/",
            proxy=f"http://foo:b%3Dar@{_HOST}:{_PORT}",
        )

        body = await response.to_array()
        assert body["HTTP_PROXY_AUTHORIZATION"] == "Basic Zm9vOmI9YXI="

        with pytest.MonkeyPatch.context() as environment:
            environment.setenv("http_proxy", _BASE_URI)
            response = await client.request("GET", f"{_BASE_URI}/")
            body = await response.to_array()
            assert body["HTTP_HOST"] == f"{_HOST}:{_PORT}"
            assert _PROXIED_URI.match(_expect(body["REQUEST_URI"], str))

        response = await client.request("GET", f"{_BASE_URI}/301/proxy", proxy=_BASE_URI)

        body = await response.to_array()
        assert body["HTTP_HOST"] == f"{_HOST}:{_PORT}"
        assert _PROXIED_URI.match(_expect(body["REQUEST_URI"], str))

    async def test_no_proxy(self) -> None:
        """A host the environment exempts is reached directly, proxy option or not."""
        with pytest.MonkeyPatch.context() as environment:
            environment.setenv("no_proxy", f"example.com, {_HOST}")

            client = self.create_client()
            response = await client.request("GET", f"{_BASE_URI}/", proxy=_BASE_URI)

            body = await response.to_array()

            assert body["SERVER_PROTOCOL"] == "HTTP/1.1"
            assert body["REQUEST_URI"] == "/"
            assert body["REQUEST_METHOD"] == "GET"

    async def test_auto_encoding_request(self) -> None:
        """A client asks for a compressed body by itself, and hands it over decoded."""
        client = self.create_client()
        response = await client.request("GET", _BASE_URI)

        assert response.get_status_code() == 200

        assert _header(response, "vary") == ["Accept-Encoding"]
        assert "gzip" in _header(response, "content-encoding")[0]

        body = await response.to_array()

        assert "gzip" in _expect(body["HTTP_ACCEPT_ENCODING"], str)

    async def test_base_uri(self) -> None:
        """A relative URL is resolved against the base, traversal included."""
        client = self.create_client()
        response = await client.request("GET", "../404", base_uri=f"{_BASE_URI}/abc/")

        assert response.get_status_code() == 404
        assert _header(response, "content-type") == ["application/json"]

    async def test_query(self) -> None:
        """Query parameters are merged into the ones the URL already carried."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/?a=a", query={"b": "b"})

        body = await response.to_array()
        assert body["REQUEST_METHOD"] == "GET"
        assert body["REQUEST_URI"] == "/?a=a&b=b"

    async def test_informational_response(self) -> None:
        """A 1xx ahead of the real status is read past, not answered with."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/103")

        assert await response.get_content() == b"Here the body"
        assert response.get_status_code() == 200

    async def test_informational_response_stream(self) -> None:
        """A run reports the 1xx and its headers, then the response it came ahead of."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/103")

        chunks: list[ChunkInterface] = []
        async for _paired, chunk in client.stream(response):
            chunks.append(chunk)

        informational = chunks[0].get_informational_status()
        assert informational is not None
        assert informational[0] == 103
        assert informational[1]["link"] == [
            "</style.css>; rel=preload; as=style",
            "</script.js>; rel=preload; as=script",
        ]
        assert chunks[1].is_first()
        assert chunks[2].get_content() == b"Here the body"
        assert chunks[3].is_last()
        assert chunks[3].get_informational_status() is None

        assert _header_names(response) == ["date", "content-length"]
        assert "Link: </style.css>; rel=preload; as=style" in _info_lines(response)

    async def test_userland_encoding_request(self) -> None:
        """Asking for an encoding outright hands the body over as it arrived."""
        client = self.create_client()
        response = await client.request("GET", _BASE_URI, headers={"Accept-Encoding": "gzip"})

        assert _header(response, "vary") == ["Accept-Encoding"]
        assert "gzip" in _header(response, "content-encoding")[0]

        content = await response.get_content()
        assert content[:1] == b"\x1f"

        body = _decode_object(gzip.decompress(content))
        assert body["HTTP_ACCEPT_ENCODING"] == "gzip"

    async def test_gzip_broken(self) -> None:
        """A body compressed only in name fails the transfer."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/gzip-broken")

        with pytest.raises(TransportError):
            _ = await response.get_content()

    async def test_max_duration(self) -> None:
        """A transfer outlasting its whole-request limit ends there, however much arrives."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/max-duration", max_duration=0.1)

        start = time.monotonic()

        with pytest.raises(TransportError):
            _ = await response.get_content()

        assert time.monotonic() - start < 10

    async def test_max_connect_duration_info(self) -> None:
        """The connect limit is something the transfer info reports back."""
        client = self.create_client()
        response = await client.request("GET", f"{_BASE_URI}/", max_connect_duration=10.0)

        assert _info(response, "max_connect_duration", float) == 10.0
        assert response.get_status_code() == 200

    async def test_max_connect_duration(self) -> None:
        """Connecting is given its own limit, well short of the idle one."""
        client = self.create_client()

        start = time.monotonic()

        with pytest.raises(TransportError):
            _ = await client.request(
                "GET",
                "http://10.255.255.1/",
                max_connect_duration=0.1,
                timeout=10,
            )

        duration = time.monotonic() - start

        assert duration < 2, "should give up long before the 10s idle timeout"
        assert duration > 0.05, "should take at least some time before giving up"

    async def test_with_options(self) -> None:
        """Options become the defaults of a new client, and leave this one as it was."""
        client = self.create_client()
        scoped = client.with_options(base_uri=f"{_BASE_URI}/")

        assert scoped is not client
        assert type(scoped) is type(client)

        response = await scoped.request("GET", "/")
        assert response.get_status_code() == 200

    async def test_bind_to_port(self) -> None:
        """A request sent from a named local port arrives from it."""
        client = self.create_client()
        response = await client.request("GET", _BASE_URI, bindto="127.0.0.1:9876")
        _ = response.get_status_code()

        variables = await response.to_array()

        assert variables["REMOTE_ADDR"] == "127.0.0.1"
        assert variables["REMOTE_PORT"] == "9876"

    async def test_bind_to_port_v6(self) -> None:
        """The same, over IPv6."""
        server = TestHttpServer(host=_IPV6_HOST, port=_IPV6_PORT)
        server.start()
        try:
            client = self.create_client()
            response = await client.request(
                "GET",
                f"http://[{_IPV6_HOST}]:{_IPV6_PORT}",
                bindto=f"[{_IPV6_HOST}]:9876",
            )
            _ = response.get_status_code()

            variables = await response.to_array()

            assert variables["REMOTE_ADDR"] == _IPV6_HOST
            assert variables["REMOTE_PORT"] == "9876"
        finally:
            server.stop()

    @staticmethod
    async def _expect_timeout(client: HttpClientInterface, port: int) -> None:
        """Make a request whose head never arrives, and expect it to say so."""
        with pytest.raises(TransportError):
            _ = await client.request(
                "GET",
                f"http://{_HOST}:{port}/timeout-header",
                timeout=0.25,
            )
