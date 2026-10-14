"""Configuration for :class:`~xtr_http_client.bundle.http_client_bundle.HttpClientBundle`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import final

from xtr_http_client.exception import InvalidArgumentError

from .client_options_config import ClientOptionsConfig
from .scoped_client_config import ScopedClientConfig

__all__ = ["HttpClientConfig"]


def _no_scoped_clients() -> dict[str, ScopedClientConfig]:
    """The empty set of services a zero-config application starts with."""
    return {}


@final
@dataclass(frozen=True, slots=True)
class HttpClientConfig:
    """The application's default client, and one more per service it calls.

    Buildable with no arguments: the zero-config path is one client sending
    requests as they are given, over connections opened when the first
    request is made.

    ```python
    HttpClientConfig(
        default_options=ClientOptionsConfig(
            timeout=10, retry_failed=RetryFailedConfig(enabled=True)
        ),
        scoped_clients={
            "github": ScopedClientConfig(
                base_uri="https://api.github.com/", auth_bearer=env("GITHUB_TOKEN")
            ),
        },
    )
    ```

    Attributes:
        max_host_connections: How many connections one pool may hold at once.
        default_options: What every request starts from, and the layers the
            default client — and every scoped one leaving them unset — is
            wrapped in.
        scoped_clients: A client per service, by the name it is qualified by.
        mock_response_factory: Answer every request from a
            :class:`~xtr_http_client.MockHttpClient` — an empty 200 until a test
            scripts it — instead of the network.
        tracing: Wrap every client in a
            :class:`~xtr_http_client.TraceableHttpClient`, which writes down
            each request made through it.
    """

    max_host_connections: int = 6
    default_options: ClientOptionsConfig = field(default_factory=ClientOptionsConfig)
    scoped_clients: Mapping[str, ScopedClientConfig] = field(default_factory=_no_scoped_clients)
    mock_response_factory: bool = False
    tracing: bool = False

    def __post_init__(self) -> None:
        """Refuse a scoped client with no name, or one that cannot take what it inherits.

        Raises:
            InvalidArgumentError: When the configuration cannot be used.
        """
        for name, scoped in self.scoped_clients.items():
            if name == "":
                raise InvalidArgumentError("A scoped HTTP client needs a name, got an empty one.")
            # Validated as it is built: retries falling back to other base URIs
            # are only usable by a client with a base URI of its own.
            _ = scoped.inheriting(self.default_options)
