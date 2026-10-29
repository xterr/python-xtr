"""The ``make:*`` commands, one module each.

Nothing is imported here: each module imports the library it writes code for,
and the bundle loads it only when that library's bundle is active.
"""

from __future__ import annotations

__all__: list[str] = []
