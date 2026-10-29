"""What the error tests share."""

from __future__ import annotations

import pytest


@pytest.fixture
def secret() -> str:
    """A value shaped like a credential, planted where data could reach an error.

    Every error test looks for it in the error's message and representation:
    finding it there means a value someone sent would end up in a log.
    """
    return "s3cr3t-t0ken-4f9a"
