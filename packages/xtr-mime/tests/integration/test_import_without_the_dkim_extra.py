"""The package imports with no dkim extra, and a DKIM signer then says which extra it needs.

The development environment installs the extra, so a fresh interpreter that cannot import
dkimpy or cryptography is the one way to keep the path without it covered.
"""

from __future__ import annotations

import subprocess
import sys

BLOCK_THE_EXTRA = """
import sys
from importlib.abc import MetaPathFinder

BLOCKED = ("dkim", "cryptography")


class BlockExtra(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ModuleNotFoundError(f"{fullname} is blocked for this run", name=fullname)
        return None


sys.meta_path.insert(0, BlockExtra())
for name in BLOCKED:
    sys.modules[name] = None
"""

SIGN = """
import xtr_mime
from xtr_mime.crypto import DkimOptions, DkimSigner

assert "dkim" not in sys.modules or sys.modules["dkim"] is None
try:
    DkimSigner("key", "example.com", "sf", default_options=DkimOptions())
except xtr_mime.LogicError as error:
    print(error)
"""


def test_without_the_extra_the_package_imports_and_the_signer_names_the_extra() -> None:
    completed = subprocess.run(  # noqa: S603 -- a fixed script on sys.executable, nothing untrusted
        [sys.executable, "-c", BLOCK_THE_EXTRA + SIGN],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (
        completed.stdout == 'The "dkim" extra is required to use DKIM: uv add "xtr-mime[dkim]".\n'
    )
