"""Driver errors as each database raises them, for the paths that act on one."""

from __future__ import annotations

from typing import final

from sqlalchemy.exc import DBAPIError, OperationalError


@final
class SqlStateError(Exception):
    """A PostgreSQL driver's error: an SQLSTATE beside its message."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__(f"sqlstate {sqlstate}")
        self.sqlstate: str = sqlstate


def deadlock() -> DBAPIError:
    """A deadlock, the conflict two workers run into."""
    return OperationalError("UPDATE", None, SqlStateError("40P01"))


def lost_connection() -> DBAPIError:
    """A connection the pool found dead and threw away."""
    return DBAPIError(
        "DELETE", None, Exception("server closed the connection"), connection_invalidated=True
    )


def refusal() -> DBAPIError:
    """Anything else a database refuses: a constraint, a permission."""
    return DBAPIError("SELECT", None, Exception("permission denied"))
