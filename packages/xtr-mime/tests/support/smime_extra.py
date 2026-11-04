"""Skip a test, or a test module, that needs the smime extra when it is not installed.

The suite also runs against the package's own dependencies alone, without extras; a module
importing cryptography calls :func:`require_smime_extra` before it does, and a test needing it
in a module that does not marks itself with :data:`needs_smime_extra`.
"""

from __future__ import annotations

from importlib.util import find_spec

import pytest

__all__ = ["needs_smime_extra", "require_smime_extra"]

needs_smime_extra = pytest.mark.skipif(
    find_spec("cryptography") is None, reason='needs the "smime" extra'
)
"""Skip the test it marks unless cryptography imports."""


def require_smime_extra() -> None:
    """Skip the calling module unless cryptography imports."""
    if find_spec("cryptography") is None:
        pytest.skip('needs the "smime" extra', allow_module_level=True)
