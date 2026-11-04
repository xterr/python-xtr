"""Skip a test, or a test module, that needs the dkim extra when it is not installed.

The suite also runs against the package's own dependencies alone, without extras; a module
importing dkimpy or cryptography calls :func:`require_dkim_extra` before it does, and a test
needing them in a module that does not marks itself with :data:`needs_dkim_extra`.
"""

from __future__ import annotations

from importlib.util import find_spec

import pytest

__all__ = ["dkim_extra_installed", "needs_dkim_extra", "require_dkim_extra"]


def dkim_extra_installed() -> bool:
    """Tell whether dkimpy and cryptography both import."""
    return find_spec("dkim") is not None and find_spec("cryptography") is not None


needs_dkim_extra = pytest.mark.skipif(not dkim_extra_installed(), reason='needs the "dkim" extra')
"""Skip the test it marks unless dkimpy and cryptography both import."""


def require_dkim_extra() -> None:
    """Skip the calling module unless dkimpy and cryptography both import."""
    if not dkim_extra_installed():
        pytest.skip('needs the "dkim" extra', allow_module_level=True)
