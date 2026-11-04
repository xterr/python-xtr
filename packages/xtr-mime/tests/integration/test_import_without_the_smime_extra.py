"""The package imports with no smime extra, and an S/MIME signer or encrypter names the extra.

The development environment installs the extra, so a fresh interpreter that cannot import
cryptography is the one way to keep the path without it covered.
"""

from __future__ import annotations

import subprocess
import sys

BLOCK_THE_EXTRA = """
import sys
from importlib.abc import MetaPathFinder


class BlockExtra(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] == "cryptography":
            raise ModuleNotFoundError(f"{fullname} is blocked for this run", name=fullname)
        return None


sys.meta_path.insert(0, BlockExtra())
sys.modules["cryptography"] = None
"""

BUILD = """
import xtr_mime
from xtr_mime.crypto import SMimeEncrypter, SMimeSigner
from xtr_mime.part import SMimePart

assert sys.modules["cryptography"] is None
_ = SMimePart("body", "application", "pkcs7-mime", {}).to_string()
for build in (lambda: SMimeSigner("sign.crt", "sign.key"), lambda: SMimeEncrypter("x.crt")):
    try:
        build()
    except xtr_mime.LogicError as error:
        print(error)
"""


def test_without_the_extra_the_package_imports_and_s_mime_names_the_extra() -> None:
    completed = subprocess.run(  # noqa: S603 -- a fixed script on sys.executable, nothing untrusted
        [sys.executable, "-c", BLOCK_THE_EXTRA + BUILD],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == (
        'The "smime" extra is required to use S/MIME: uv add "xtr-mime[smime]".\n' * 2
    )
