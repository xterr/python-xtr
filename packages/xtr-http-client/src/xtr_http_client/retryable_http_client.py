"""The client that makes a request again when it is worth making again."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import anyio
from typing_extensions import Unpack, override
from xtr_http_client_contracts import HttpClientInterface
from xtr_service_contracts import ResetInterface

from .exception import InvalidArgumentError, TransportError
from .internal.option_merge import as_options
from .internal.retry_count_response import with_retry_count
from .internal.retry_delay import retry_after_ms
from .internal.retry_options import (
    base_uri_rotation,
    replays_body,
    replays_request,
    retries,
    with_base_uri,
)
from .retry.generic_retry_strategy import GenericRetryStrategy
from .retry.retry_context import RetryContext

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping
    from typing import Self

    from xtr_http_client_contracts import HttpResponseInterface, RequestOptions
    from xtr_http_message_contracts import RequestInterface
    from xtr_logging_contracts import LoggerInterface

    from .retry.retry_strategy_interface import RetryStrategyInterface

    _Attempt = Callable[[Mapping[str, object], int], Awaitable[HttpResponseInterface]]

__all__ = ["RetryableHttpClient"]


@final
class RetryableHttpClient(HttpClientInterface, ResetInterface):
    """Wraps a client and makes the request again while a strategy says to.

    A server that answered 503, or a connection that never came up, has not
    answered the question that was asked — and often answers it on the next
    try. Written at the call site that is a loop, a counter and a delay around
    every request; here it is the client, so the code calling out is unchanged
    and the decision lives in one place.

    ```python
    client = RetryableHttpClient(inner, max_retries=2)
    async with await client.request("GET", "https://example.com/orders") as response:
        orders = await response.to_array()
    ```

    What is retried, and how long is waited between tries, is the
    :class:`RetryStrategyInterface
    <xtr_http_client.retry.retry_strategy_interface.RetryStrategyInterface>`'s
    — :class:`GenericRetryStrategy
    <xtr_http_client.retry.generic_retry_strategy.GenericRetryStrategy>` by
    default, which retries the status codes worth retrying and backs off
    between attempts. A ``Retry-After`` header wins over its delay: a server
    saying when to come back is better informed than a client guessing.

    Two things bound it. ``max_retries`` — which a request may lower or raise
    through the ``max_retries`` option — is how many *further* attempts are
    allowed, so the request is made at most that many times plus one; and a
    body that cannot be produced twice is sent once, because a second attempt
    would send a request that is not the one that failed.

    The ``base_uri`` option may name several, and then each attempt moves one
    along it — the way a client is pointed at a second host rather than at the
    host that has just refused. The response handed back reports how many
    tries it took, under the ``retry_count`` entry of ``get_info()``.
    """

    __slots__ = ("_base_uris", "_client", "_logger", "_max_retries", "_sleep", "_strategy")

    def __init__(
        self,
        client: HttpClientInterface,
        strategy: RetryStrategyInterface | None = None,
        max_retries: int = 3,
        logger: LoggerInterface | None = None,
        sleep: Callable[[float], Awaitable[None]] = anyio.sleep,
    ) -> None:
        """Retry what ``client`` sends, as often as ``max_retries`` allows.

        Args:
            client: The client every attempt is handed to.
            strategy: What decides whether an attempt is worth repeating.
                ``None`` takes :class:`GenericRetryStrategy
                <xtr_http_client.retry.generic_retry_strategy.GenericRetryStrategy>`
                as it comes.
            max_retries: How many further attempts a request may have. Zero
                or less is a client that passes everything straight through.
            logger: Where each retry is reported, at info level. ``None``
                reports none.
            sleep: What waiting between attempts is done with. Only worth
                passing to make a test's waits instant.
        """
        self._client = client
        self._strategy: RetryStrategyInterface = (
            GenericRetryStrategy() if strategy is None else strategy
        )
        self._max_retries = max_retries
        self._logger = logger
        self._sleep = sleep
        self._base_uris: tuple[str, ...] = ()

    @override
    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Make a request for ``method`` and ``url``, again while that is worth doing.

        Args:
            method: The HTTP method, in upper case.
            url: The URL to request, absolute or relative to a ``base_uri``.
            **options: How the request is to be made. ``max_retries`` is
                this client's own and is not passed on.

        Returns:
            What the last attempt answered.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option, and
                when the strategy will not decide.
            TransportError: When the last attempt brought back no answer.
        """

        async def attempt(sent: Mapping[str, object], count: int) -> HttpResponseInterface:
            del count

            return await self._client.request(method, url, **as_options(sent))

        return await self._attempted(
            attempt,
            method,
            url,
            dict(options),
            replayable=replays_body(options),
        )

    @override
    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Send ``request``, again while that is worth doing.

        Args:
            request: The request to send. Every attempt sends this very
                request, its body rewound first.
            **options: What the request leaves out. ``max_retries`` is this
                client's own and is not passed on.

        Returns:
            What the last attempt answered.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option, and
                when the strategy will not decide.
            TransportError: When the last attempt brought back no answer.
        """

        async def attempt(sent: Mapping[str, object], count: int) -> HttpResponseInterface:
            body = request.get_body()
            if count and body.is_seekable():
                await body.rewind()

            return await self._client.send_request(request, **as_options(sent))

        return await self._attempted(
            attempt,
            request.get_method(),
            str(request.get_uri()),
            dict(options),
            replayable=replays_body(options) and replays_request(request),
        )

    @override
    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        """Return a copy around a wrapped client whose defaults have ``options`` over them.

        ``base_uri`` and ``max_retries`` stay here rather than going on: a
        list of base URIs is this client's to walk, and how many attempts are
        allowed is not something the client behind it can act on.

        Args:
            **options: The defaults of the wrapped client of the copy.

        Returns:
            A new client, retrying by the same strategy; this one is left as
            it was.

        Raises:
            InvalidArgumentError: When an option is invalid.
        """
        given: dict[str, object] = dict(options)
        base_uris = self._base_uris

        if "base_uri" in given:
            rotation = base_uri_rotation(given["base_uri"])
            base_uris = () if rotation is None else rotation
            if rotation is not None:
                del given["base_uri"]

        max_retries = retries(given.pop("max_retries", None), self._max_retries)
        narrowed = type(self)(
            self._client.with_options(**as_options(given)),
            self._strategy,
            max_retries,
            self._logger,
            self._sleep,
        )
        narrowed._base_uris = base_uris  # noqa: SLF001 — same class, seeded as a field

        return narrowed

    @override
    def reset(self) -> None:
        """Reset the wrapped client.

        Nothing here outlives a request — how many attempts are allowed and
        what decides them are configuration — so there is only the client
        behind to pass this on to.
        """
        if isinstance(self._client, ResetInterface):
            self._client.reset()

    async def _attempted(
        self,
        attempt: _Attempt,
        method: str,
        url: str,
        options: dict[str, object],
        *,
        replayable: bool,
    ) -> HttpResponseInterface:
        """Make the request, and make it again while the strategy says to."""
        base_uris = self._base_uris
        if "base_uri" in options:
            rotation = base_uri_rotation(options["base_uri"])
            base_uris = () if rotation is None else rotation

        max_retries = retries(options.pop("max_retries", None), self._max_retries)
        if max_retries <= 0 or not replayable:
            return await attempt(with_base_uri(options, base_uris, 0), 0)

        count = 0
        while True:
            sent = with_base_uri(options, base_uris, count)
            try:
                response = await attempt(sent, count)
            except TransportError as error:
                context = RetryContext(method, url, as_options(sent), count, None)
                if count >= max_retries or not await self._retries_error(context, error):
                    raise
                count += 1
                await self._paused(
                    count,
                    self._strategy.get_delay(context, None, error),
                    f": {error}",
                )
                continue

            context = RetryContext(method, url, as_options(sent), count, response)
            if count >= max_retries:
                return _answer(response, count)

            retry, content = await self._decided(context, response)
            if not retry:
                return _answer(response, count)

            delay = retry_after_ms(response)
            if delay is None:
                delay = self._strategy.get_delay(context, content, None)

            count += 1
            await response.cancel()
            await self._paused(count, delay, f", status code: {context.get_status_code()}")

    async def _decided(
        self,
        context: RetryContext,
        response: HttpResponseInterface,
    ) -> tuple[bool, bytes | None]:
        """Whether to try again, and the body that had to be read to say so.

        Raises:
            InvalidArgumentError: When the strategy asks for the body and
                then will not decide with it either, which leaves nobody
                having said whether to try again.
        """
        decision = await self._strategy.should_retry(context, None, None)
        if decision is not None:
            return decision, None

        content = await response.get_content(throw=False)
        decision = await self._strategy.should_retry(context, content, None)
        if decision is None:
            raise InvalidArgumentError(self._undecided("a body"))

        return decision, content

    async def _retries_error(self, context: RetryContext, error: TransportError) -> bool:
        """Whether an attempt that brought back nothing is worth making again.

        Raises:
            InvalidArgumentError: When the strategy will not decide, which it
                cannot defer here: there is no body to come back with.
        """
        decision = await self._strategy.should_retry(context, None, error)
        if decision is None:
            raise InvalidArgumentError(self._undecided("an error"))

        return decision

    async def _paused(self, count: int, delay: int, reason: str) -> None:
        """Report the retry about to be made, then wait for it."""
        if self._logger is not None:
            message = f"Try #{{count}} after {{delay}}ms{reason}"
            self._logger.info(message, {"count": count, "delay": delay})

        await self._sleep(delay / 1000)

    def _undecided(self, asked_with: str) -> str:
        """The message for a strategy that answered neither yes nor no."""
        return (
            f'The "{type(self._strategy).__qualname__}.should_retry()" method must not '
            f"return None when called with {asked_with}."
        )


def _answer(response: HttpResponseInterface, count: int) -> HttpResponseInterface:
    """The response as the caller gets it, saying how many tries it took."""
    if count:
        return with_retry_count(response, count)

    return response
