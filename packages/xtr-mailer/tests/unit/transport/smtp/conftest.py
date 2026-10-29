from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.certificates import Certificate, make_certificate

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def certificate(tmp_path: Path) -> Certificate:
    return make_certificate(tmp_path)
