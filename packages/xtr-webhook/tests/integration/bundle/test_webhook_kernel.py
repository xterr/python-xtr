"""End-to-end: an application listing WebhookBundle receives and sends webhooks."""

from __future__ import annotations

import hmac

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup
from xtr_messenger import HandlersFailedError, MessageBusInterface
from xtr_remote_event import RemoteEvent

from tests.fixtures.app_webhook import services
from tests.fixtures.app_webhook.config import PLAIN_SECRET
from tests.support.serving import serving
from xtr_webhook.client.request_parser import RequestParser
from xtr_webhook.exception import PrivateNetworkError
from xtr_webhook.messenger import SendWebhookMessage
from xtr_webhook.subscriber import Subscriber

pytestmark = pytest.mark.anyio

APP = "tests.fixtures.app_webhook"
GUARDED_APP = "tests.fixtures.app_guarded"

BODY = b'{"foo":"bar"}'
JSON_HEADERS = {"Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def _clear_recordings() -> None:
    services.CAPTURED.clear()
    services.CONSUMED.clear()


def _application() -> FastAPI:
    app = FastAPI()
    setup(app, Kernel(APP, env="test"))
    return app


def _legacy_signature(secret: bytes, event: bytes, event_id: bytes, body: bytes) -> str:
    return "sha256=" + hmac.new(secret, event + event_id + body, "sha256").hexdigest()


async def test_an_unknown_type_is_answered_404_through_the_served_endpoint() -> None:
    app = _application()

    async with serving(app) as client:
        response = await client.post("/webhook/unknown", content=BODY, headers=JSON_HEADERS)

    assert response.status_code == 404
    assert response.text == "No webhook parser found for the type given in the URL."


async def test_a_wrong_signature_is_refused_through_the_served_endpoint() -> None:
    app = _application()
    headers = {
        **JSON_HEADERS,
        "Webhook-Signature": _legacy_signature(b"not-the-secret", b"the-event", b"the-id", BODY),
        "Webhook-Event": "the-event",
        "Webhook-Id": "the-id",
    }

    async with serving(app) as client:
        response = await client.post("/webhook/plain", content=BODY, headers=headers)

    assert response.status_code == 406
    assert response.text == "Signature is wrong."


async def test_an_incoming_webhook_reaches_its_consumer_through_the_served_endpoint() -> None:
    app = _application()
    headers = {**JSON_HEADERS, "X-Secret": "the-secret"}

    async with serving(app) as client:
        response = await client.post("/webhook/test", content=BODY, headers=headers)

    assert response.status_code == 202
    assert [RemoteEvent("parsed", "the-id", {"foo": "bar"})] == services.CONSUMED


async def test_a_route_without_a_parser_uses_the_bundles_own_request_parser() -> None:
    app = _application()
    headers = {
        **JSON_HEADERS,
        "Webhook-Signature": _legacy_signature(
            PLAIN_SECRET.encode(), b"the-event", b"the-id", BODY
        ),
        "Webhook-Event": "the-event",
        "Webhook-Id": "the-id",
    }

    async with serving(app) as client:
        response = await client.post("/webhook/plain", content=BODY, headers=headers)

    assert response.status_code == 202
    assert [RemoteEvent("the-event", "the-id", {"foo": "bar"})] == services.CONSUMED


async def test_outgoing_webhooks_are_posted_with_signed_headers() -> None:
    async with await Kernel(APP, env="test").boot() as booted:
        bus = await booted.container.get(MessageBusInterface)
        _ = await bus.dispatch(
            SendWebhookMessage(
                Subscriber("https://example.com/hook", "the-secret"),
                RemoteEvent("the-event", "the-id", {"foo": "bar"}),
            )
        )

    (request,) = services.CAPTURED
    assert str(request.url) == "https://example.com/hook"
    assert request.content == BODY
    assert request.headers["Webhook-Event"] == "the-event"
    assert request.headers["Webhook-Id"] == "the-id"
    assert "Webhook-Timestamp" in request.headers
    assert request.headers["Webhook-Signature"] == _legacy_signature(
        b"the-secret", b"the-event", b"the-id", BODY
    )


async def test_the_request_parser_answers_the_webhook_target() -> None:
    async with await Kernel(APP, env="test").boot() as booted:
        probe = await booted.container.get(services.ParserProbe)

    assert isinstance(probe.parser, RequestParser)


async def test_the_guarded_client_refuses_a_private_address() -> None:
    async with await Kernel(GUARDED_APP, env="test").boot() as booted:
        bus = await booted.container.get(MessageBusInterface)

        with pytest.raises(HandlersFailedError) as caught:
            _ = await bus.dispatch(
                SendWebhookMessage(
                    Subscriber("http://127.0.0.1/", "the-secret"),
                    RemoteEvent("the-event", "the-id", {"foo": "bar"}),
                )
            )

    (failure,) = caught.value.errors.values()
    assert isinstance(failure, PrivateNetworkError)
    assert str(failure) == (
        'The host "127.0.0.1" resolves to "127.0.0.1", which is in a private network.'
    )
