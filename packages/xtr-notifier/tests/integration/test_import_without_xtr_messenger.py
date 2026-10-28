"""The notifier imports and sends with no message bus installed.

The dev group installs xtr-messenger, so every other test in this suite runs
with it there. A fresh interpreter that cannot import it is the only way to keep
the bus-less path covered.
"""

from __future__ import annotations

import subprocess
import sys

BLOCK_THE_BUS = """
import sys
from importlib.abc import MetaPathFinder
from importlib.util import find_spec


class BlockBus(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "xtr_messenger" or fullname.startswith("xtr_messenger."):
            raise ModuleNotFoundError("xtr_messenger is blocked for this run", name=fullname)
        return None


sys.meta_path.insert(0, BlockBus())
sys.modules["xtr_messenger"] = None

if find_spec("xtr_messenger") is not None:
    raise AssertionError("xtr_messenger stayed discoverable: this run proves nothing")
"""

SENDS = """
import anyio

import xtr_notifier.event_listener
import xtr_notifier.testing
from xtr_notifier import Notifier, Transport
from xtr_notifier.channel import ChatChannel
from xtr_notifier.notification import Notification
from xtr_notifier.transport import TransportFactoryDiscovery

transport = Transport(
    discovery=TransportFactoryDiscovery(TransportFactoryDiscovery.CHATTER_GROUP)
).from_string("null://null")
anyio.run(Notifier({"chat": ChatChannel(transport)}).send, Notification("Hi", channels=["chat"]))
"""


def test_the_package_imports_and_sends_without_the_message_bus() -> None:
    completed = subprocess.run(  # noqa: S603 -- a fixed script on sys.executable, nothing untrusted
        [sys.executable, "-c", BLOCK_THE_BUS + SENDS],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
