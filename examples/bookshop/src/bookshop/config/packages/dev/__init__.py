"""The ``dev`` environment folder: configuration imported only when ``APP_ENV`` is ``dev``.

Every module here is imported after the common modules of ``config/packages/``, so what it
configures wins over them, and never in any other environment. That is where a development-only
bundle — ``MakerBundle`` — is configured: its package is a development dependency, not installed
in production, and a module directly under ``config/packages/`` importing it would stop a
production start.
"""

from __future__ import annotations

__all__: list[str] = []
