"""A client of its own for one service: where it is, and what reaching it takes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import ClassVar, final

from xtr_http_client.exception import InvalidArgumentError

from .client_options_config import ClientOptionsConfig
from .retry_failed_config import RetryFailedConfig

__all__ = ["ScopedClientConfig"]


@final
@dataclass(frozen=True, slots=True)
class ScopedClientConfig(ClientOptionsConfig):
    r"""A client whose options apply to the URLs of one service.

    A request whose URL ``scope`` matches from its start — or which falls under
    ``base_uri``, when there is no scope — starts from these options, and a
    relative URL resolves against ``base_uri``. Left as they are,
    ``retry_failed`` and ``rate_limiter`` are the default options' own.

    ```python
    ScopedClientConfig(
        base_uri="https://api.github.com/",
        headers={"Accept": "application/vnd.github+json"},
        auth_bearer=env("GITHUB_TOKEN"),
    )
    ```

    Attributes:
        scope: A regular expression a URL must match from its start for these
            options to apply.
        base_uri: What a relative URL resolves against, and — with no
            ``scope`` — what a URL must start with to be in scope.
        auth_basic: Credentials for basic authentication; kept out of the
            ``repr``.
        auth_bearer: A token to send as a bearer credential; kept out of the
            ``repr``.
        query: Parameters merged into the query of every URL resolved against
            ``base_uri``.
        mock_response_factory: ``True`` answers this client's requests from
            the mock transport, ``False`` sends them for real, whatever the
            bundle's own setting is; ``None`` follows it.
    """

    _NOT_OPTIONS: ClassVar[frozenset[str]] = frozenset(
        {"retry_failed", "rate_limiter", "scope", "mock_response_factory"}
    )

    scope: str | None = None
    base_uri: str | None = None
    auth_basic: str | tuple[str] | tuple[str, str] | None = field(default=None, repr=False)
    auth_bearer: str | None = field(default=None, repr=False)
    query: Mapping[str, str | int | float | Sequence[str | int | float]] | None = None
    mock_response_factory: bool | None = None

    def __post_init__(self) -> None:
        """Refuse a client that says nothing about which URLs are its own.

        Raises:
            InvalidArgumentError: When neither a scope nor a base URI is given,
                or ``query`` or fallback base URIs come without a base URI.
        """
        if self.scope is None and self.base_uri is None:
            raise InvalidArgumentError('Either "scope" or "base_uri" should be defined.')
        if self.query and self.base_uri is None:
            raise InvalidArgumentError('"query" applies to "base_uri" but no base URI is defined.')
        if self.retry_failed.base_uris and self.base_uri is None:
            raise InvalidArgumentError(
                '"retry_failed.base_uris" lists the URIs to fall back to, so a "base_uri" '
                "must be defined as well."
            )

    def inheriting(self, defaults: ClientOptionsConfig) -> ScopedClientConfig:
        """Return this client with the retries and the limiter it left to ``defaults``.

        Inherited whole, not field by field: a client that configures its own
        retries says everything about them.

        Raises:
            InvalidArgumentError: When what it inherits cannot be used with it —
                fallback base URIs, for a client with no base URI.
        """
        return replace(
            self,
            retry_failed=(
                self.retry_failed
                if self.retry_failed != RetryFailedConfig()
                else defaults.retry_failed
            ),
            rate_limiter=self.rate_limiter
            if self.rate_limiter is not None
            else defaults.rate_limiter,
        )
