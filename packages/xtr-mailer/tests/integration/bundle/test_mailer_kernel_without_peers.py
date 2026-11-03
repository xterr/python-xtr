"""The bundle builds, boots and sends with any of its optional peers not installed.

The development environment installs every peer, so a fresh interpreter that cannot import them
is the one way to keep the paths without them covered.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

_PEERS = (
    "xtr_console",
    "xtr_event_dispatcher",
    "xtr_http_client",
    "xtr_messenger",
    "xtr_rate_limiter",
)

_BLOCK = """
import sys
from importlib.abc import MetaPathFinder

BLOCKED = {blocked!r}


class Block(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ModuleNotFoundError(f"{{fullname}} is blocked for this run", name=fullname)
        return None


sys.meta_path.insert(0, Block())
for name in BLOCKED:
    sys.modules[name] = None
"""

_SEND = """
import asyncio

from xtr_dependency_injection import Kernel
from xtr_mime import Email

from xtr_mailer import Mailer, MailerInterface
from xtr_mailer.bundle import MailerBundle


async def main() -> None:
    bundles = {MailerBundle: {"all": True}}
    kernel = Kernel("xtr_mailer.bundle", env="test", bundles=bundles, resources=())
    async with await kernel.boot() as booted:
        mailer = await booted.container.get(MailerInterface)
        await mailer.send(Email().from_("a@example.com").to("b@example.com").text("Hi"))
    assert isinstance(mailer, Mailer)
    print("sent")


asyncio.run(main())
"""


@pytest.mark.parametrize("blocked", [(peer,) for peer in _PEERS] + [_PEERS])
def test_the_bundle_sends_without_the_peers_installed(blocked: tuple[str, ...]) -> None:
    completed = subprocess.run(  # noqa: S603 -- a fixed script on sys.executable, nothing untrusted
        [sys.executable, "-c", _BLOCK.format(blocked=blocked) + _SEND],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "sent\n"
