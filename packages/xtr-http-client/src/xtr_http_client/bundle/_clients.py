"""What the bundle registers: the transports, and every client built over one.

A client is a transport wrapped in the layers its configuration turns on, built
by a factory of its own. What that factory is handed depends on the
configuration — the transport it sends through, the limiter it waits its turn
from, the strategy deciding its retries — so the annotations the container reads
are written onto it here rather than in its signature, and a dependency it does
not need is given as ``None`` rather than asked for.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Collection, Sequence
from typing import TYPE_CHECKING, Annotated

from xtr_dependency_injection import ServiceConfigurator, Target, named_factory
from xtr_http_client_contracts import HttpClientInterface

from xtr_http_client.httpx_http_client import HttpxHttpClient
from xtr_http_client.mock_http_client import MockHttpClient
from xtr_http_client.retry.generic_retry_strategy import (
    DEFAULT_RETRY_STATUS_CODES,
    GenericRetryStrategy,
)
from xtr_http_client.retry.retry_strategy_interface import RetryStrategyInterface
from xtr_http_client.retryable_http_client import RetryableHttpClient
from xtr_http_client.scoping_http_client import ScopingHttpClient
from xtr_http_client.throttling_http_client import ThrottlingHttpClient
from xtr_http_client.traceable_http_client import TraceableHttpClient

from .http_client_config import HttpClientConfig

if TYPE_CHECKING:
    from xtr_rate_limiter import RateLimiterFactoryInterface

    from .client_options_config import ClientOptionsConfig
    from .retry_failed_config import RetryFailedConfig
    from .scoped_client_config import ScopedClientConfig

__all__ = ["register_client", "register_transports"]


def register_transports(services: ServiceConfigurator, mocked: Collection[bool]) -> None:
    """Register the transports the clients send through — only the ones some client uses.

    Args:
        services: Where the bundle registers its services.
        mocked: Whether each client answers from the mock transport.
    """
    if not all(mocked):
        _ = services.set(_httpx_transport)
    if any(mocked):
        _ = services.set(_mock_transport)


def register_client(
    services: ServiceConfigurator,
    name: str | None,
    options: ClientOptionsConfig,
    *,
    mocked: bool,
) -> None:
    """Register the client ``name`` — the default one for ``None`` — as ``options`` build it.

    Args:
        services: Where the bundle registers its services.
        name: The scoped client's name, which qualifies it; ``None`` for the
            default client.
        options: Its options, with what it inherits already filled in.
        mocked: Whether it answers from the mock transport.
    """
    annotations: dict[str, object] = {
        "config": HttpClientConfig,
        "transport": MockHttpClient if mocked else HttpxHttpClient,
        "return": HttpClientInterface,
    }
    unused: dict[str, object] = {}
    if options.rate_limiter is None:
        unused["limiters"] = None
    else:
        annotations["limiters"] = _limiters(options.rate_limiter)
    retry = options.retry_failed
    if retry.enabled and retry.retry_strategy is not None:
        annotations["strategy"] = Annotated[RetryStrategyInterface, Target(retry.retry_strategy)]
    else:
        unused["strategy"] = None

    factory = _client_factory(name)
    factory.__annotations__ = annotations
    definition = services.set(
        named_factory(factory, "http_client" if name is None else f"http_client_{name}"),
        qualifier=name,
    )
    if unused:
        _ = definition.set_arguments(unused)


async def _httpx_transport(config: HttpClientConfig) -> AsyncIterator[HttpxHttpClient]:
    """Build the transport opening real connections, and close them with the container.

    The default options are the transport's own, so every client sending
    through it starts from them.
    """
    transport = HttpxHttpClient(config.default_options.to_options(), config.max_host_connections)
    try:
        yield transport
    finally:
        await transport.aclose()


def _mock_transport() -> MockHttpClient:
    """Build the transport answering from a script: an empty 200 until a test sets one."""
    return MockHttpClient()


def _limiters(rate_limiter: str) -> object:
    """Return the annotation asking for the limiter factory ``rate_limiter`` names."""
    # The throttling extra is optional: a client is only paced while the rate
    # limiter bundle is active, which proves it installed.
    from xtr_rate_limiter import RateLimiterFactoryInterface  # noqa: PLC0415

    return Annotated[RateLimiterFactoryInterface, Target(rate_limiter)]


def _client_factory(name: str | None) -> Callable[..., HttpClientInterface]:
    """Return the factory of the client ``name``, one function per client.

    Its options are read from the configuration it is handed, so an ``env()``
    placeholder in them is read when the client is built.
    """

    def http_client(
        config: HttpClientConfig,
        transport: HttpClientInterface,
        limiters: RateLimiterFactoryInterface | None,
        strategy: RetryStrategyInterface | None,
    ) -> HttpClientInterface:
        client = (
            transport if limiters is None else ThrottlingHttpClient(transport, limiters.create())
        )
        if name is None:
            retry = config.default_options.retry_failed
            client = _retried(client, retry, strategy, retry.base_uris)
        else:
            scoped = config.scoped_clients[name].inheriting(config.default_options)
            client = _scoped(client, scoped, strategy)

        return TraceableHttpClient(client) if config.tracing else client

    return http_client


def _scoped(
    client: HttpClientInterface,
    scoped: ScopedClientConfig,
    strategy: RetryStrategyInterface | None,
) -> HttpClientInterface:
    """Wrap ``client`` in the scope of one service, and in its retries.

    Retries go inside the scope, unless they move along fallback base URIs:
    the scope resolves a URL and consumes ``base_uri``, so a base URI chosen
    beneath it would never be applied — the retries wrap the scope instead,
    and the scope matches every URI they may move to.
    """
    retry = scoped.retry_failed
    base_uris = [] if scoped.base_uri is None else [scoped.base_uri, *retry.base_uris]
    walks = len(base_uris) > 1
    inner = client if walks else _retried(client, retry, strategy)
    options = scoped.to_options()

    if scoped.scope is not None:
        scoping = ScopingHttpClient(inner, {scoped.scope: options}, scoped.scope)
    elif walks:
        scoping = ScopingHttpClient.for_base_uris(inner, base_uris, options)
    else:
        scoping = ScopingHttpClient.for_base_uri(inner, base_uris[0], options)

    return _retried(scoping, retry, strategy, base_uris) if walks else scoping


def _retried(
    client: HttpClientInterface,
    retry: RetryFailedConfig,
    strategy: RetryStrategyInterface | None,
    base_uris: Sequence[str] = (),
) -> HttpClientInterface:
    """Wrap ``client`` in the retries ``retry`` turns on, walking ``base_uris`` if any."""
    if not retry.enabled:
        return client

    retrying = RetryableHttpClient(
        client,
        strategy if strategy is not None else _generic_strategy(retry),
        retry.max_retries,
    )

    return retrying.with_options(base_uri=list(base_uris)) if base_uris else retrying


def _generic_strategy(retry: RetryFailedConfig) -> GenericRetryStrategy:
    """Build the strategy ``retry``'s numbers describe."""
    return GenericRetryStrategy(
        DEFAULT_RETRY_STATUS_CODES if retry.http_codes is None else retry.http_codes,
        retry.delay,
        retry.multiplier,
        retry.max_delay,
        retry.jitter,
    )
