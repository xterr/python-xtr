"""Bookshop: a complete application on the xtr packages — one kernel, a console and a web front.

Every entry point shares :data:`bookshop.kernel.kernel`:

- ``python -m bookshop`` (``uv run bookshop``) — the console;
- ``python -m bookshop.web`` (``uv run bookshop-web``) — a small HTTP server;
- ``python -m bookshop.worker`` — a message worker.

The package is scanned by the kernel: importing it declares nothing by side effect, and
every module is imported by the scan, sorted by name.
"""

from __future__ import annotations

__all__: list[str] = []
