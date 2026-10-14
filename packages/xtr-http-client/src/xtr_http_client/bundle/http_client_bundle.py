"""The xtr-http-client bundle: the application's HTTP client, and one more per service.

An application listing :class:`HttpClientBundle` gets an
:class:`~xtr_http_client_contracts.HttpClientInterface` — the default client — and,
for every scoped client its :class:`HttpClientConfig` names, another one qualified
by that name. Each is a transport the bundle owns, wrapped in the layers its
configuration turns on, from the inside out: the pace of an xtr-rate-limiter
limiter, the options of one service, another try at what failed, and a record of
every request.

Every client shares one transport — :class:`~xtr_http_client.HttpxHttpClient`, or
:class:`~xtr_http_client.MockHttpClient` for a client answering from a script — so
they share its connections. Nothing is opened until a request is made, and the
connections are closed with the container.
"""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    required_bundle,
)

from xtr_http_client.exception import InvalidArgumentError

from ._clients import register_client, register_transports
from .http_client_config import HttpClientConfig

__all__ = ["HttpClientBundle"]


@final
@required_bundle("xtr_rate_limiter.bundle:RateLimiterBundle", ignore_on_invalid=True)
@as_bundle("http_client", config=HttpClientConfig)
class HttpClientBundle(Bundle[HttpClientConfig]):
    """Turns an :class:`HttpClientConfig` into the default client and a client per service."""

    @override
    def load_extension(
        self,
        config: HttpClientConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register every client, and the transports they send through.

        Raises:
            InvalidArgumentError: When a client is paced by a rate limiter while
                the rate limiter bundle is not active.
        """
        pacing = bundle_active(builder, "rate_limiter")
        defaults = config.default_options
        _check_pace("The default HTTP client", defaults.rate_limiter, pacing)
        register_client(services, None, defaults, mocked=config.mock_response_factory)

        mocked = [config.mock_response_factory]
        for name, scoped in config.scoped_clients.items():
            client = scoped.inheriting(defaults)
            mock = scoped.mock_response_factory
            mocked.append(config.mock_response_factory if mock is None else mock)
            _check_pace(f'The "{name}" HTTP client', client.rate_limiter, pacing)
            register_client(services, name, client, mocked=mocked[-1])

        register_transports(services, mocked)


def _check_pace(owner: str, rate_limiter: str | None, pacing: bool) -> None:
    """Refuse a rate limiter nothing can provide.

    Raises:
        InvalidArgumentError: When ``rate_limiter`` is named while the rate
            limiter bundle is not active.
    """
    if rate_limiter is not None and not pacing:
        raise InvalidArgumentError(
            f'{owner} is paced by the "{rate_limiter}" rate limiter, but the rate limiter '
            f'bundle is not active: install "xtr-http-client[throttling]".'
        )
