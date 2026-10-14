"""The package imports, and its bundle builds, with no HTTP client installed.

The dev group installs xtr-http-client, so every other test in this suite runs
with it there. A fresh interpreter that cannot import it is the only way to keep
the client-less path covered; nothing in the installed environment can express
"absent". Only xtr-http-client is blocked: its contracts are a dependency of
this package, and stay.
"""

from __future__ import annotations

import subprocess
import sys

BLOCK_THE_CLIENT = """
import sys
from importlib.abc import MetaPathFinder
from importlib.util import find_spec


class BlockClient(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "xtr_http_client" or fullname.startswith("xtr_http_client."):
            raise ModuleNotFoundError("xtr_http_client is blocked for this run", name=fullname)
        return None


sys.meta_path.insert(0, BlockClient())
sys.modules["xtr_http_client"] = None

if find_spec("xtr_http_client") is not None:
    raise AssertionError("xtr_http_client stayed discoverable: this run proves nothing")
"""

IMPORTS = """
import xtr_webhook
import xtr_webhook.bundle
import xtr_webhook.messenger
import xtr_webhook.server
"""

BUILDS = """
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
        assert not booted.container.has(TransportInterface), "a transport came without a client"
        assert booted.container.has(WebhookController), "the controller must not need a client"
    finally:
        await booted.shutdown()


anyio.run(main)
"""


def _run(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- a fixed script on sys.executable, nothing untrusted
        [sys.executable, "-c", BLOCK_THE_CLIENT + script],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_package_and_its_sending_side_import_without_the_http_client() -> None:
    completed = _run(IMPORTS)

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_without_the_http_client_the_bundle_builds_with_no_transport_but_the_controller() -> None:
    completed = _run(BUILDS)

    assert completed.returncode == 0, completed.stderr or completed.stdout
