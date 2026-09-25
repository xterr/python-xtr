from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_clock import Clock

pytest_plugins = ["xtr_clock.pytest_plugin"]

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _isolate_clock() -> Generator[None, None, None]:
    """Keep a test that installs a clock from reaching the next one.

    Reinstalling the clock already in force changes nothing, and leaving the
    scope restores both the clock for this context and the process-wide
    fallback that `Clock.set` writes.
    """
    with Clock.using(Clock.get()):
        yield
