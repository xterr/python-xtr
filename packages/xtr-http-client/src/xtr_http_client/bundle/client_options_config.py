"""What every request a configured client makes starts from."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, ClassVar, cast

from xtr_http_client.internal.option_merge import as_options

from .retry_failed_config import RetryFailedConfig

if TYPE_CHECKING:
    from xtr_http_client_contracts import RequestOptions

__all__ = ["ClientOptionsConfig"]


@dataclass(frozen=True, slots=True)
class ClientOptionsConfig:
    """The request options a client starts from, and the layers wrapped around it.

    Each option field is the request option of the same name, and ``None``
    leaves it to the client's own default. ``retry_failed`` and
    ``rate_limiter`` are not request options: they say whether the client
    makes a failed request again, and which rate it is held to.

    Attributes:
        headers: Headers to send, a mapping of name to one value or several.
        max_redirects: How many redirects to follow.
        http_version: The HTTP version to ask for.
        timeout: How long the transfer may go quiet for, in seconds.
        max_duration: How long a whole request and response may take, in seconds.
        max_connect_duration: How long connecting may take, in seconds.
        resolve: Host to IP address, used instead of asking a resolver.
        proxy: The proxy to go through, as a URL.
        verify_peer: Whether to check that the peer's certificate is trusted.
        verify_host: Whether to check that the certificate is for the host.
        cafile: A file of certificates to trust instead of the defaults.
        capath: A directory of certificates to trust instead of the defaults.
        local_cert: A client certificate to present.
        local_pk: The private key of ``local_cert``, when it is kept apart.
        passphrase: The passphrase of ``local_pk``; kept out of the ``repr``.
        extra: Additional options a client may ignore.
        retry_failed: Whether and how a failed request is made again.
        rate_limiter: The name of the xtr-rate-limiter limiter every request
            waits its turn from; needs the ``throttling`` extra.
    """

    _NOT_OPTIONS: ClassVar[frozenset[str]] = frozenset({"retry_failed", "rate_limiter"})

    headers: Mapping[str, str | Sequence[str]] | None = None
    max_redirects: int | None = None
    http_version: str | None = None
    timeout: float | None = None
    max_duration: float | None = None
    max_connect_duration: float | None = None
    resolve: Mapping[str, str] | None = None
    proxy: str | None = None
    verify_peer: bool | None = None
    verify_host: bool | None = None
    cafile: str | None = None
    capath: str | None = None
    local_cert: str | None = None
    local_pk: str | None = None
    passphrase: str | None = field(default=None, repr=False)
    extra: Mapping[str, object] | None = None
    retry_failed: RetryFailedConfig = field(default_factory=RetryFailedConfig)
    rate_limiter: str | None = None

    def to_options(self) -> RequestOptions:
        """Return the request options that are set, as a client takes them."""
        options: dict[str, object] = {}
        for entry in fields(self):
            value = cast("object", getattr(self, entry.name))
            if entry.name not in self._NOT_OPTIONS and value is not None:
                options[entry.name] = value

        return as_options(options)
