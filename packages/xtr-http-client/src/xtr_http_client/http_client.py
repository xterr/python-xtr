"""Where a client comes from when the caller has no opinion about which one."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import Unpack

from .httpx_http_client import HttpxHttpClient

if TYPE_CHECKING:
    from xtr_http_client_contracts import HttpClientInterface, RequestOptions

__all__ = ["HttpClient"]


@final
class HttpClient:
    """One call that hands back a client, so nothing has to name an implementation.

    Code that calls out depends on the interface. Code that *builds* a client
    has to pick something, and picking is a decision worth making in one
    place: this is that place.

    ```python
    from xtr_http_client import HttpClient

    client = HttpClient.create(base_uri="https://example.com/", timeout=5)
    ```

    It is not a client itself and holds nothing; there is nothing to keep an
    instance of.
    """

    __slots__ = ()

    @staticmethod
    def create(
        max_host_connections: int = 6,
        **default_options: Unpack[RequestOptions],
    ) -> HttpClientInterface:
        """Return a client whose requests start from ``default_options``.

        Args:
            max_host_connections: How many connections one pool may hold at
                once.
            **default_options: What every request the client makes starts
                from, over the contract's own defaults.

        Returns:
            A client, typed as the interface: what is behind it is this
            package's decision, not the caller's.

        Raises:
            InvalidArgumentError: When an option is not one the client knows.
        """
        return HttpxHttpClient(default_options, max_host_connections)
