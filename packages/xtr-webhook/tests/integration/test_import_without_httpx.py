"""The package imports with no HTTP client installed.

The dev group installs httpx, so every other test in this suite runs with it
there. A fresh interpreter that cannot import it is the only way to keep the
client-less path covered; nothing in the installed environment can express
"absent". Only httpx is blocked: anyio cannot be, because xtr-clock — a hard
dependency — imports it.
"""

from __future__ import annotations

import subprocess
import sys

SCRIPT = """
import sys
from importlib.abc import MetaPathFinder


class BlockHttpx(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "httpx" or fullname.startswith("httpx."):
            raise ModuleNotFoundError("httpx is blocked for this run", name=fullname)
        return None


sys.meta_path.insert(0, BlockHttpx())

try:
    import httpx
except ModuleNotFoundError:
    pass
else:
    raise AssertionError("a blocked module stayed importable: this run proves nothing")

import xtr_webhook
import xtr_webhook.server
"""


def test_the_package_and_its_sending_side_import_without_the_http_client() -> None:
    completed = subprocess.run(  # noqa: S603 -- a fixed script on sys.executable, nothing untrusted
        [sys.executable, "-c", SCRIPT],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
