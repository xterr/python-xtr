"""The client that answers from a script, so a test never leaves the process."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import Unpack, override
from xtr_http_client_contracts import HttpClientInterface, RequestOptions
from xtr_http_message import Request
from xtr_service_contracts import ResetInterface

from .exception import InvalidArgumentError, TransportError
from .http_client_mixin import HttpClientMixin
from .internal.debug_type import debug_type
from .internal.httpx_request import target_url
from .response.mock_response import MockResponse

if TYPE_CHECKING:
    from xtr_http_message_contracts import RequestInterface

__all__ = ["MockHttpClient", "ResponseFactory"]

ScriptedFactory = Callable[[str, str, RequestOptions], "MockResponse | Awaitable[MockResponse]"]
"""Something called with a request, that says what is to come back for it."""

ResponseFactory = MockResponse | ScriptedFactory | Iterable[MockResponse | ScriptedFactory]
"""Where a scripted client's answers come from: one, many, or one per request."""

_EMPTY: Final = "The response factory iterator passed to MockHttpClient is empty."
_EXHAUSTED: Final = (
    "No more response left in the response factory iterator passed to MockHttpClient: "
    "the number of requests exceeds the number of responses."
)

# Nothing a factory could legitimately be, so it can stand for "the iterator
# had nothing left" without `None` — a perfectly good thing to yield — meaning
# that too.
_NOTHING: Final = object()


@final
class MockHttpClient(HttpClientMixin, HttpClientInterface, ResetInterface):
    """Answers every request from what a test wrote out, and opens no connection.

    It is the same client as any other here — the options it refuses, the
    defaults it starts from and the way a request and its options are merged
    are all the ones a real transfer uses — with the transfer replaced by a
    script. So a test exercises the code that calls out, down to the options
    it passed, without a server to point it at.

    ```python
    client = MockHttpClient([MockResponse(b"first"), MockResponse(b"second")])
    async with await client.request("GET", "/orders") as response:
        assert await response.get_content() == b"first"
    assert client.get_requests_count() == 1
    ```

    What the answers come from is whatever a test finds easiest to write:

    - nothing, and every request is answered with an empty 200;
    - one :class:`MockResponse <xtr_http_client.response.mock_response.MockResponse>`,
      which answers one request, and a second request is a mistake, reported
      as the script running out;
    - an iterable of them, one per request, in order — a request past the end
      of it is a mistake and is reported as one, since a test that makes more
      requests than it wrote answers for is no longer testing what it says;
    - a callable, which is handed the method, the URL and the merged options
      and says what to answer with — the way to assert on the request that was
      made, and to answer differently depending on it. It may be async.

    An iterable may hold callables too, so one request in a sequence can be
    answered that way while the rest are written out.

    Nothing is followed and nothing is resolved: a 3xx is the answer, and a
    relative URL is resolved against ``base_uri`` — which starts at
    ``https://example.com`` so a test can say ``/orders`` and mean something.
    """

    __slots__ = ("_factory", "_requests_count")

    _factory: ScriptedFactory | Iterator[MockResponse | ScriptedFactory] | None

    def __init__(
        self,
        response_factory: ResponseFactory | None = None,
        base_uri: str | None = "https://example.com",
    ) -> None:
        """Start from ``response_factory``, which nothing is taken from until asked.

        Args:
            response_factory: Where the answers come from.
            base_uri: What a relative URL is resolved against. ``None`` leaves
                a relative URL unresolvable, which is then refused.
        """
        super().__init__({"base_uri": base_uri})
        self._requests_count = 0
        self.set_response_factory(response_factory)

    def set_response_factory(self, response_factory: ResponseFactory | None = None) -> None:
        """Answer from ``response_factory`` from now on.

        What was left of the previous one is dropped, and the count of
        requests already made is kept: a test that changes its mind about the
        answers has not unmade the requests.

        Args:
            response_factory: Where the answers come from.
        """
        if isinstance(response_factory, MockResponse):
            # A single answer is one item of a script, so it answers one request.
            self._factory = iter([response_factory])
        elif isinstance(response_factory, Iterable):
            # Taken one at a time from here on, so a generator is not drawn
            # on until the request its answer is for.
            self._factory = iter(response_factory)
        else:
            self._factory = response_factory

    def get_requests_count(self) -> int:
        """Return how many requests this client has been asked to make."""
        return self._requests_count

    @override
    async def reset(self) -> None:
        """Forget how many requests were made, leaving the answers as they are."""
        self._requests_count = 0

    @override
    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> MockResponse:
        """Answer a request for ``method`` and ``url`` from the script.

        Args:
            method: The HTTP method, in upper case.
            url: The URL to request, absolute or relative to ``base_uri``.
            **options: How the request would have been made.

        Returns:
            The scripted answer, issued for this request.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option.
            TransportError: When the script says the transfer fails, or has
                no answer left to give.
        """
        self.validate_method(method)

        return await self.send_request(Request(method, url), **options)

    @override
    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> MockResponse:
        """Answer ``request`` from the script, the options filling what it leaves out.

        Args:
            request: The request that would have been sent.
            **options: What the request leaves out.

        Returns:
            The scripted answer, issued for this request.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option, and
                for a body given both with the request and as an option.
            TransportError: When the script says the transfer fails, has no
                answer left to give, or gives something that is not an answer.
        """
        self.validate_options(options)
        self.validate_method(request.get_method())
        merged = self.merge_default_options(options, self._default_options)
        self.validate_auth(merged)
        self.validate_body(merged)

        method = request.get_method()
        url = _resolved(request, merged)
        answer = await self._scripted(method, url, merged)
        self._requests_count += 1

        if not isinstance(answer, MockResponse):
            raise TransportError(
                "The response factory passed to MockHttpClient must return/yield an "
                f'instance of MockResponse, "{debug_type(answer)}" given.'
            )

        return answer.issue(method, url, merged)

    async def _scripted(self, method: str, url: str, options: Mapping[str, object]) -> object:
        """Whatever the script offers for this request, answer or not."""
        factory = self._factory

        if factory is None:
            return MockResponse()
        if callable(factory):
            return await _called(factory, method, url, options)

        return await _called(_taken(factory, self._requests_count), method, url, options)


def _taken(factory: Iterator[object], made: int) -> object:
    """The next thing the script offers.

    Raises:
        TransportError: When there is nothing left — which is a test that
            wrote no answers at all, or fewer than it makes requests, and
            those are two different mistakes.
    """
    offered = next(factory, _NOTHING)
    if offered is _NOTHING:
        raise TransportError(_EXHAUSTED if made else _EMPTY)

    return offered


async def _called(
    offered: object,
    method: str,
    url: str,
    options: Mapping[str, object],
) -> object:
    """``offered`` itself, or what it answers with when it is something to call."""
    if not callable(offered):
        return offered

    said = offered(method, url, cast("RequestOptions", options))
    if isinstance(said, Awaitable):
        return await said

    return said


def _resolved(request: RequestInterface, options: Mapping[str, object]) -> str:
    """The URL the request is for, resolved and with ``query`` merged in.

    Raises:
        InvalidArgumentError: When the URL is relative and there is no base to
            resolve it against, since what was asked for then names nothing.
    """
    url = target_url(request, options)
    if url.is_relative_url:
        raise InvalidArgumentError(
            f'Invalid URL "{url}": it is relative, and no "base_uri" option '
            "says what to resolve it against."
        )

    return str(url)
