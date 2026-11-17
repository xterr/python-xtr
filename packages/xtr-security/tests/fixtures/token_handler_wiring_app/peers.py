"""The client every handler of the fixture reaches its server with, as a bundle of its own."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_http_client_contracts import HttpClientInterface

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = ["ServerClientBundle"]


def _client() -> HttpClientInterface:
    # Every answer is a transport failure: the server cannot be reached.
    return MockHttpClient(MockResponse(b"", {"error": "the server is unreachable"}))


@as_bundle("token_handler_wiring_client")
class ServerClientBundle(Bundle):
    """Registers the HTTP client the token handlers reach their servers through."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, builder
        _ = services.set(_client)
