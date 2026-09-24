from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.stdlib import preserved_stdlib_logging

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def stdlib_logging() -> Iterator[None]:
    """Give back every standard logger as it was, whatever the test changed."""
    yield from preserved_stdlib_logging()
