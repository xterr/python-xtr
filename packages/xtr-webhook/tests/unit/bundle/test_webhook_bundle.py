from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config

from tests.support.recording_message_bus import RecordingMessageBus
from xtr_webhook.bundle import WebhookBundle, WebhookConfig
from xtr_webhook.bundle.webhook_bundle import _webhook_controller
from xtr_webhook.controller.webhook_controller import WebhookController
from xtr_webhook.exception import LogicError
from xtr_webhook.server.transport_interface import TransportInterface

pytestmark = pytest.mark.anyio


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(WebhookBundle)


async def test_the_controller_factory_is_refused_before_the_bundle_booted() -> None:
    build = _webhook_controller(WebhookBundle())

    with pytest.raises(LogicError, match="has no container"):
        _ = await build(WebhookConfig(), RecordingMessageBus())


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
