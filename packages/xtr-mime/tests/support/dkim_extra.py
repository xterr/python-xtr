"""Skip a test module that needs the dkim extra when it is not installed.

The suite also runs against the package's own dependencies alone, without extras; a module
importing dkimpy or cryptography calls :func:`require_dkim_extra` before it does.
"""

from __future__ import annotations

from importlib.util import find_spec

import pytest

__all__ = ["require_dkim_extra"]


def require_dkim_extra() -> None:
    """Skip the calling module unless dkimpy and cryptography both import."""
    if find_spec("dkim") is None or find_spec("cryptography") is None:
        pytest.skip('needs the "dkim" extra', allow_module_level=True)
