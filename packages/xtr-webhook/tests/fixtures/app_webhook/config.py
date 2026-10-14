"""The application's webhook routes, its clients and its bus, so a test sees every effect."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_http_client.bundle import HttpClientConfig, ScopedClientConfig
from xtr_messenger import MessageBusConfig, TransportConfig
from xtr_remote_event.messenger import ConsumeRemoteEventMessage

from tests.support.secret_header_request_parser import SecretHeaderRequestParser
from xtr_webhook.bundle import RouteConfig, WebhookConfig
from xtr_webhook.messenger import SendWebhookMessage

PARSED_TYPE = "test"
PLAIN_TYPE = "plain"
PARSED_SECRET = "the-secret"
PLAIN_SECRET = "plain-secret"
APP_CLIENT = "app_client"
"""The client webhooks are sent through, named so a test can tell it from the default one."""


@configure
def webhook() -> WebhookConfig:
    """Route one type to a custom parser and one to the bundle's own, sending by the app client."""
    return WebhookConfig(
        http_client=APP_CLIENT,
        routing={
            PARSED_TYPE: RouteConfig(parser=SecretHeaderRequestParser, secret=PARSED_SECRET),
            PLAIN_TYPE: RouteConfig(secret=PLAIN_SECRET),
        },
    )


@configure
def http_client() -> HttpClientConfig:
    """Answer every request from the mock transport; the app client says it was the one used."""
    return HttpClientConfig(
        mock_response_factory=True,
        scoped_clients={
            APP_CLIENT: ScopedClientConfig(scope="https://", headers={"X-Client": APP_CLIENT}),
        },
    )


@configure
def messenger() -> MessageBusConfig:
    """Route both messages to ``sync://``, so a test sees what handling them did."""
    return MessageBusConfig(
        transports={"sync": TransportConfig("sync://")},
        routing={ConsumeRemoteEventMessage: "sync", SendWebhookMessage: "sync"},
    )
