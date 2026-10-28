"""What carries an email to its destination, and the DSN that picks it."""

from __future__ import annotations

from .dsn import Dsn, DsnOption

__all__ = ["Dsn", "DsnOption"]
