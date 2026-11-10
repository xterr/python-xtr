"""Every instant a stored credential's column hands its database driver, recorded and judged.

The SQLite type the tests run on turns a value into text before the cursor sees it, so what a
stricter driver would be handed is read at the column instead: the value
:class:`~xtr_security_oauth2_server.persistence.type.utc_datetime.UtcDateTime` returns. It must
be exactly a plain naive UTC ``datetime`` — one driver refuses an aware value, two convert the
offset they are handed, and one does not recognise a ``datetime`` subclass at all.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from xtr_security_oauth2_server.persistence.type.utc_datetime import UtcDateTime

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest
    from sqlalchemy import Dialect

__all__ = ["BOUND_ZONE", "assert_naive_utc", "record_bound_instants"]

#: The zone the recording runs the machine in: east of UTC, so a value labelled with the local
#: zone is hours away from the instant it carries.
BOUND_ZONE = "Europe/Bucharest"


def record_bound_instants(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Run in :data:`BOUND_ZONE` and return the list every bound instant is appended to."""
    monkeypatch.setenv("TZ", BOUND_ZONE)
    bound: list[object] = []
    original = UtcDateTime.process_bind_param

    def recording(self: UtcDateTime, value: datetime | None, dialect: Dialect) -> datetime | None:
        handed = original(self, value, dialect)
        if handed is not None:
            bound.append(handed)
        return handed

    monkeypatch.setattr(UtcDateTime, "process_bind_param", recording)
    return bound


def assert_naive_utc(bound: Sequence[object]) -> None:
    """Assert something was bound, and every value bound is exactly a plain naive ``datetime``."""
    assert bound, "no instant was bound"
    for value in bound:
        assert type(value) is datetime, f"{value!r} is not exactly a datetime"
        assert value.tzinfo is None, f"{value!r} carries a zone"
