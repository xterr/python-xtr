"""Deliberately broken pieces, so ``bookshop demo:errors`` can show every guided error.

``misconfigured`` is scanned with the application: its services compile, and fail only when
built — an environment variable is read when needed, never while the kernel builds.
``broken_app`` and ``broken_config`` are excluded from the application's scan
(``bookshop.kernel``); ``demo:errors`` builds a throwaway kernel over each.
"""

from __future__ import annotations

__all__: list[str] = []
