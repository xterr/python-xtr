"""The container's table becomes the process's default; every test here puts the old one back."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_mime import MimeTypes

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _keep_the_default_table() -> Iterator[None]:
    kept = MimeTypes._default
    yield
    MimeTypes._default = kept
