from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config

from tests.fixtures.app_webhook.config import PARSED_TYPE, PLAIN_TYPE
from tests.support.secret_header_request_parser import SecretHeaderRequestParser
from xtr_webhook.bundle import WebhookBundle
from xtr_webhook.client import RequestParser
from xtr_webhook.controller.webhook_controller import WebhookController
from xtr_webhook.exception import LogicError
from xtr_webhook.server.transport_interface import TransportInterface

pytestmark = pytest.mark.anyio


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(WebhookBundle)


async def test_the_controller_serves_the_routed_types_and_no_other() -> None:
    kernel = Kernel("tests.fixtures.app_webhook", env="test")

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
    kernel = Kernel("tests.fixtures.app_webhook", env="test")

    async with await kernel.boot() as booted:
        parsers = (await booted.container.get(WebhookController))._parsers

        with pytest.raises(LogicError, match='"stranger"'):
            _ = await parsers.get("stranger")


def _finds_nothing(name: str) -> None:
    del name


async def test_without_httpx_the_transport_stays_out_but_the_controller_stays_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("xtr_webhook.bundle.webhook_bundle.find_spec", _finds_nothing)

    kernel = Kernel(
        "xtr_webhook.bundle", env="test", bundles={WebhookBundle: {"all": True}}, resources=()
    )
    booted = await kernel.boot()
    try:
        assert not booted.container.has(TransportInterface)
        assert booted.container.has(WebhookController)
    finally:
        await booted.shutdown()
