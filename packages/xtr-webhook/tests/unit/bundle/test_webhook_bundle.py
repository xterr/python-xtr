from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config
from xtr_http_client import NoPrivateNetworkHttpClient
from xtr_http_client_contracts import HttpClientInterface

from tests.fixtures.app_guarded.config import GUARDED_CLIENT
from tests.fixtures.app_webhook.config import APP_CLIENT, PARSED_TYPE, PLAIN_TYPE
from tests.support.secret_header_request_parser import SecretHeaderRequestParser
from xtr_webhook.bundle import WebhookBundle
from xtr_webhook.client import RequestParser
from xtr_webhook.controller.webhook_controller import WebhookController
from xtr_webhook.exception import LogicError
from xtr_webhook.server import Transport
from xtr_webhook.server.transport_interface import TransportInterface

pytestmark = pytest.mark.anyio

APP = "tests.fixtures.app_webhook"
GUARDED_APP = "tests.fixtures.app_guarded"


def _bundle_alone() -> Kernel:
    return Kernel(
        "xtr_webhook.bundle", env="test", bundles={WebhookBundle: {"all": True}}, resources=()
    )


def _finds_nothing(name: str) -> None:
    del name


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(WebhookBundle)


async def test_the_controller_serves_the_routed_types_and_no_other() -> None:
    kernel = Kernel(APP, env="test")

    async with await kernel.boot() as booted:
        parsers = (await booted.container.get(WebhookController))._parsers
        parsed = await parsers.get(PARSED_TYPE)
        plain = await parsers.get(PLAIN_TYPE)

    assert parsers.has(PARSED_TYPE)
    assert parsers.has(PLAIN_TYPE)
    assert not parsers.has("webhook")
    assert isinstance(parsed, SecretHeaderRequestParser)
    assert isinstance(plain, RequestParser)
    assert set(parsers.provided_services()) == {PARSED_TYPE, PLAIN_TYPE}


async def test_asking_for_a_type_the_routing_does_not_name_is_a_logic_error() -> None:
    kernel = Kernel(APP, env="test")

    async with await kernel.boot() as booted:
        parsers = (await booted.container.get(WebhookController))._parsers

        with pytest.raises(LogicError, match='"stranger"'):
            _ = await parsers.get("stranger")


async def test_with_no_client_named_the_transport_sends_through_the_default_one() -> None:
    async with await _bundle_alone().boot() as booted:
        transport = await booted.container.get(TransportInterface)
        default = await booted.container.get(HttpClientInterface)

    assert isinstance(transport, Transport)
    assert transport._client is default


async def test_a_named_client_is_the_one_the_transport_sends_through() -> None:
    async with await Kernel(APP, env="test").boot() as booted:
        transport = await booted.container.get(TransportInterface)
        named = await booted.container.get(HttpClientInterface, APP_CLIENT)

    assert isinstance(transport, Transport)
    assert transport._client is named


async def test_the_guard_wraps_the_client_the_transport_sends_through() -> None:
    async with await Kernel(GUARDED_APP, env="test").boot() as booted:
        transport = await booted.container.get(TransportInterface)
        named = await booted.container.get(HttpClientInterface, GUARDED_CLIENT)

    assert isinstance(transport, Transport)
    assert isinstance(transport._client, NoPrivateNetworkHttpClient)
    assert transport._client._client is named


async def test_without_the_http_client_the_transport_stays_out_but_the_controller_stays_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("xtr_webhook.bundle.webhook_bundle.find_spec", _finds_nothing)

    async with await _bundle_alone().boot() as booted:
        assert not booted.container.has(TransportInterface)
        assert booted.container.has(WebhookController)


def test_without_the_http_client_the_guard_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("xtr_webhook.bundle.webhook_bundle.find_spec", _finds_nothing)

    with pytest.raises(LogicError) as caught:
        _ = Kernel(GUARDED_APP, env="test").build()

    assert str(caught.value) == (
        'Configuring "no_private_network" requires xtr-http-client; '
        'install it with uv add "xtr-webhook[client]".'
    )
