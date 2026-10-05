from __future__ import annotations

from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    # tmp_path projects stay in the package's own .tmp/, never in the system temp
    # directory, wherever pytest is started from. An explicit --basetemp still wins.
    chosen: object = config.getoption("basetemp")
    if chosen is None:
        scratch = Path(__file__).resolve().parents[1] / ".tmp"
        scratch.mkdir(exist_ok=True)
        config.option.basetemp = str(scratch / "pytest")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
