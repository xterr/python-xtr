"""Skip a test module that needs the smime extra when it is not installed.

The suite also runs against the package's own dependencies alone, without extras; a module
importing cryptography calls :func:`require_smime_extra` before it does.
"""

from __future__ import annotations

from importlib.util import find_spec

import pytest

__all__ = ["require_smime_extra"]


def require_smime_extra() -> None:
    """Skip the calling module unless cryptography imports."""
    if find_spec("cryptography") is None:
        pytest.skip('needs the "smime" extra', allow_module_level=True)
