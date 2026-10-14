"""The client that writes down every request made through it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, TypedDict, cast, final

from typing_extensions import Unpack, override
from xtr_http_client_contracts import HttpClientInterface, HttpResponseInterface
from xtr_service_contracts import ResetInterface

from .exception import TransportError
from .internal.option_merge import as_options

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence
    from types import TracebackType
    from typing import Self

    from xtr_http_client_contracts import RequestOptions
    from xtr_http_message_contracts import RequestInterface, StreamInterface

__all__ = ["TraceableHttpClient", "TracedRequest"]

# The options that carry what was sent, which a request may ask to be left
# out of its record.
_BODIES: Final = frozenset({"body", "json"})


class TracedRequest(TypedDict):
    """The record of one request made through a tracing client.

    Attributes:
        method: The HTTP method the request was made with.
        url: The URL it was made to, as it was asked for.
        options: The options it was made with, as they were given — without
            ``body`` and ``json`` when ``extra.trace_content`` turned the
            bodies off.
        info: What the transfer knew about itself when the response arrived.
            Empty until it arrives, and carrying ``error`` alone when nothing
            does.
        content: Every byte of the body, once the caller has read it;
            ``None`` while nobody has, and ``False`` when
            ``extra.trace_content`` turned the bodies off.
    """

    method: str
    url: str
    options: RequestOptions
    info: Mapping[str, object]
    content: bytes | bool | None


@final
class TraceableHttpClient(HttpClientInterface, ResetInterface):
    """Wraps a client and writes down every request made through it.

    "Which calls did this go on to make, with what, and what came back" is
    asked of a running application constantly — by a profiler, by a test
    asserting on a call it has no other sight of, by whoever is reading a log
    that stops short of the call. Answered at the call site that is logging
    around every request; here it is the client, so the code calling out is
    unchanged and the record is one list.

    ```python
    client = TraceableHttpClient(inner)
    async with await client.request("GET", "https://example.com/orders") as response:
        orders = await response.to_array()

    traced = client.get_traced_requests()
    assert traced[0]["method"] == "GET"
    assert traced[0]["content"] == b'{"orders": []}'
    ```

    A record is added the moment a request is made and filled in as that
    request goes on: ``info`` when the response arrives — or the error alone,
    when nothing arrives and the error is raised on — and ``content`` when the
    caller reads the body. So a trace read while a request is still being
    answered says how far it has got, rather than nothing until it is over.

    The bodies are the costly half of a record and the half most likely to
    carry a credential, so ``extra={"trace_content": False}`` leaves them out:
    the ``body`` and ``json`` that were sent are dropped from ``options``, and
    ``content`` is ``False`` rather than the bytes. Nothing is recorded at all
    for a request made while ``disabled`` says so, which is how a profiler
    that collects per request stops collecting between them.

    The record is the point, so a copy made by :meth:`with_options` shares it:
    narrowing a client for one job hands out another way of making requests,
    all of them written into the one list.
    """

    __slots__ = ("_client", "_disabled", "_traces")

    def __init__(
        self,
        client: HttpClientInterface,
        disabled: Callable[[], bool] | None = None,
    ) -> None:
        """Write down what ``client`` is asked to send, unless ``disabled`` says not to.

        Args:
            client: The client every request is handed to.
            disabled: Asked before each request whether to record it. ``None``
                records every one.
        """
        self._client = client
        self._disabled = disabled
        self._traces: list[TracedRequest] = []

    @override
    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Make a request for ``method`` and ``url``, and write it down.

        Args:
            method: The HTTP method, in upper case.
            url: The URL to request, absolute or relative to a ``base_uri``.
            **options: How the request is to be made.

        Returns:
            What the wrapped client answers, reading its body into the record
            as the caller reads it.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option.
            TransportError: When no answer came, which is written down before
                it is raised on.
        """
        if self._skipped():
            return await self._client.request(method, url, **options)

        trace = self._written(method, url, options)

        return await self._answered(trace, self._client.request(method, url, **options))

    @override
    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Send ``request``, and write it down.

        Args:
            request: The request to send, whose method and URI are what the
                record names it by.
            **options: What the request leaves out.

        Returns:
            What the wrapped client answers, reading its body into the record
            as the caller reads it.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option.
            TransportError: When no answer came, which is written down before
                it is raised on.
        """
        if self._skipped():
            return await self._client.send_request(request, **options)

        trace = self._written(request.get_method(), str(request.get_uri()), options)

        return await self._answered(trace, self._client.send_request(request, **options))

    def get_traced_requests(self) -> list[TracedRequest]:
        """Return the record of every request made through this client so far.

        Returns:
            A list of its own, so taking the record does not hand over the
            one the client goes on appending to. The records in it are the
            live ones: a request still being answered fills in the record
            this list holds.
        """
        return list(self._traces)

    @override
    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        """Return a copy around a wrapped client whose defaults have ``options`` over them.

        Args:
            **options: The defaults of the wrapped client of the copy.

        Returns:
            A new client writing into this one's record, so a request made
            through either is traced in one place; this one is left as it was.

        Raises:
            InvalidArgumentError: When an option is invalid.
        """
        narrowed = type(self)(self._client.with_options(**options), self._disabled)
        narrowed._traces = self._traces  # noqa: SLF001 — same class, sharing the one record

        return narrowed

    @override
    async def reset(self) -> None:
        """Forget every request written down, and reset the wrapped client.

        The record goes for every client sharing it, copies included: there is
        one record, and this ends the unit of work it was kept for.
        """
        self._traces.clear()

        if isinstance(self._client, ResetInterface):
            await self._client.reset()

    def _skipped(self) -> bool:
        """Whether the request about to be made is one nobody is recording."""
        return self._disabled is not None and self._disabled()

    def _written(self, method: str, url: str, options: RequestOptions) -> TracedRequest:
        """Add the record of a request about to be made, for the rest to be filled into."""
        kept = _keeps_content(options)
        trace: TracedRequest = {
            "method": method,
            "url": url,
            "options": options if kept else _without_bodies(options),
            "info": {},
            "content": None if kept else False,
        }
        self._traces.append(trace)

        return trace

    async def _answered(
        self,
        trace: TracedRequest,
        made: Awaitable[HttpResponseInterface],
    ) -> HttpResponseInterface:
        """Wait for a request, write down what came back, and keep reading recorded.

        Args:
            trace: The record of the request being made.
            made: That request, as the wrapped client is making it.

        Returns:
            The response wrapped so that reading its body writes the bytes
            down, or the response as it came when the bodies are not kept.

        Raises:
            TransportError: When no answer came, with what went wrong written
                down first — the record of a request that failed is the half
                worth having.
        """
        try:
            response = await made
        except TransportError as error:
            trace["info"] = {"error": str(error)}

            raise

        trace["info"] = _recorded_info(response)

        if trace["content"] is False:
            return response

        return _TracedResponse(response, trace)


def _keeps_content(options: RequestOptions) -> bool:
    """Whether the bodies of a request made with ``options`` are written down.

    They are, unless ``extra.trace_content`` is exactly ``False``: an entry
    meaning "do not keep this" is the one thing it says, and anything else
    there is a value for some other client to read.
    """
    extra = options.get("extra")

    return extra is None or extra.get("trace_content", True) is not False


def _without_bodies(options: RequestOptions) -> RequestOptions:
    """``options`` with what was sent dropped, for a request whose bodies are not kept."""
    return as_options({name: value for name, value in options.items() if name not in _BODIES})


def _recorded_info(response: HttpResponseInterface) -> Mapping[str, object]:
    """What a response's transfer knows about itself, as a mapping of its own."""
    whole = response.get_info()
    if isinstance(whole, Mapping):
        return dict(cast("Mapping[str, object]", whole))

    return {}


@final
class _TracedResponse(HttpResponseInterface):
    """A response that writes its body into a record once the caller reads it.

    A record is written as the request goes on, and the body is the part that
    arrives last — when the caller asks for it, which may be long after the
    response was handed over. Nothing but the caller's own read can say what
    the body was, so the read is what writes it down: everything else here is
    the wrapped response's, which keeps the one body and the one transfer
    rather than copying either.
    """

    __slots__ = ("_inner", "_trace")

    def __init__(self, inner: HttpResponseInterface, trace: TracedRequest) -> None:
        self._inner = inner
        self._trace = trace

    @override
    def get_status_code(self) -> int:
        return self._inner.get_status_code()

    @override
    def get_reason_phrase(self) -> str:
        return self._inner.get_reason_phrase()

    @override
    def with_status(self, code: int, reason_phrase: str = "") -> Self:
        return self._around(self._inner.with_status(code, reason_phrase))

    @override
    def get_protocol_version(self) -> str:
        return self._inner.get_protocol_version()

    @override
    def with_protocol_version(self, version: str) -> Self:
        return self._around(self._inner.with_protocol_version(version))

    @override
    def get_headers(self) -> Mapping[str, Sequence[str]]:
        return self._inner.get_headers()

    @override
    def has_header(self, name: str) -> bool:
        return self._inner.has_header(name)

    @override
    def get_header(self, name: str) -> Sequence[str]:
        return self._inner.get_header(name)

    @override
    def get_header_line(self, name: str) -> str:
        return self._inner.get_header_line(name)

    @override
    def with_header(self, name: str, value: str | Sequence[str]) -> Self:
        return self._around(self._inner.with_header(name, value))

    @override
    def with_added_header(self, name: str, value: str | Sequence[str]) -> Self:
        return self._around(self._inner.with_added_header(name, value))

    @override
    def without_header(self, name: str) -> Self:
        return self._around(self._inner.without_header(name))

    @override
    def get_body(self) -> StreamInterface:
        return self._inner.get_body()

    @override
    def with_body(self, body: StreamInterface) -> Self:
        return self._around(self._inner.with_body(body))

    @override
    def get_info(self, key: str | None = None) -> object:
        return self._inner.get_info(key)

    @override
    async def cancel(self) -> None:
        await self._inner.cancel()

    @override
    async def get_content(self, throw: bool = True) -> bytes:
        content = await self._inner.get_content(throw)
        self._trace["content"] = content

        return content

    @override
    async def to_array(self, throw: bool = True) -> dict[str, object]:
        # The bytes are written down before they are decoded, because they are
        # what was read whether or not they turn out to be the JSON the caller
        # read them as — and a body that would not decode is the one a trace is
        # being read to explain.
        self._trace["content"] = await self._inner.get_content(throw)

        return await self._inner.to_array(throw)

    @override
    async def __aenter__(self) -> Self:
        _ = await self._inner.__aenter__()

        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._inner.__aexit__(exc_type, exc, traceback)

    def _around(self, inner: HttpResponseInterface) -> Self:
        return type(self)(inner, self._trace)
