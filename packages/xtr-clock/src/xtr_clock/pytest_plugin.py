"""A pytest fixture that freezes the clock for one test.

Opt in from a ``conftest.py``, which is the only place this module's import
of pytest is ever paid for:

```python
pytest_plugins = ["xtr_clock.pytest_plugin"]
```

It is not registered automatically on purpose. A fixture named ``clock``
appearing in every suite that merely installs this library would collide
with the one plenty of suites already have.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .testing import mock_time

if TYPE_CHECKING:
    from collections.abc import Generator

    from .mock_clock import MockClock

__all__ = ["clock"]


@pytest.fixture
def clock() -> Generator[MockClock, None, None]:
    """Freeze the clock at the current instant, in UTC, for one test.

    The clock in force is restored afterwards, so a test that never asks for
    this fixture is unaffected by one that does.

    ```python
    def test_a_token_expires_in_an_hour(clock: MockClock) -> None:
        token = issue_token()
        clock.sleep(3599)
        assert token.is_valid()
        clock.sleep(2)
        assert not token.is_valid()
    ```
    """
    with mock_time() as frozen:
        yield frozen
