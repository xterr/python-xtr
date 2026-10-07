"""The async backends every awaitable wait is exercised on.

``sleep_async`` goes through anyio rather than straight to asyncio, so a trio
application can use these clocks too. The only way to keep that true is to
run the waits on more than one backend — on asyncio, which is always there,
and on trio when the checkout has it.
"""

from __future__ import annotations

from importlib.util import find_spec

import pytest

__all__ = ["ANYIO_BACKENDS"]

ANYIO_BACKENDS = [
    "asyncio",
    pytest.param(
        "trio",
        marks=pytest.mark.skipif(find_spec("trio") is None, reason="trio is not installed"),
    ),
]
