"""The httpx side of the bundle: registered only with the library, closed with the container.

The dev group installs httpx, so the without-httpx path runs in a fresh
interpreter where the library is made undiscoverable before anything imports
it; nothing in the installed environment can express "absent".
"""

from __future__ import annotations

import subprocess
import sys

import httpx
import pytest
from xtr_dependency_injection import Kernel

from xtr_webhook.bundle import WebhookBundle

pytestmark = pytest.mark.anyio

SCRIPT = """
import sys
from importlib.abc import MetaPathFinder
from importlib.util import find_spec


class BlockHttpx(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "httpx" or fullname.startswith("httpx."):
            raise ModuleNotFoundError("httpx is blocked for this run", name=fullname)
        return None


sys.meta_path.insert(0, BlockHttpx())
sys.modules["httpx"] = None

if find_spec("httpx") is not None:
    raise AssertionError("httpx stayed discoverable: this run proves nothing")

import anyio
from xtr_dependency_injection import Kernel

from xtr_webhook.bundle import WebhookBundle
from xtr_webhook.controller.webhook_controller import WebhookController
from xtr_webhook.server.transport_interface import TransportInterface


async def main():
    kernel = Kernel(
        "xtr_webhook.bundle", env="test", bundles={WebhookBundle: {"all": True}}, resources=()
    )
    booted = await kernel.boot()
    try:
        assert not booted.container.has(TransportInterface), "a transport slipped in without httpx"
        assert booted.container.has(WebhookController), "the controller must not need httpx"
    finally:
        await booted.shutdown()


anyio.run(main)
"""


def test_without_httpx_the_kernel_builds_with_no_transport_but_with_the_controller() -> None:
    completed = subprocess.run(  # noqa: S603 -- a fixed script on sys.executable, nothing untrusted
        [sys.executable, "-c", SCRIPT],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


async def test_the_bundle_built_client_is_closed_with_the_container() -> None:
    kernel = Kernel(
        "xtr_webhook.bundle", env="test", bundles={WebhookBundle: {"all": True}}, resources=()
    )
    booted = await kernel.boot()

    client = await booted.container.get(httpx.AsyncClient, "webhook")
    assert not client.is_closed

    await booted.shutdown()

    assert client.is_closed
