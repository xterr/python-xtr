"""A bundle whose only job is to contribute scanned resources."""

from __future__ import annotations

from typing import final

from xtr_console.bundle import ConsoleBundle
from xtr_dependency_injection import Bundle, as_bundle, required_bundle

__all__ = ["DevToolsBundle"]


@final
@required_bundle(ConsoleBundle)
@as_bundle("dev_tools", resources=("bookshop.dev_tools",))
class DevToolsBundle(Bundle):
    """An empty class: ``resources`` is all it contributes, and it takes no config.

    ``config`` is omitted, so the bundle's config is ``NoConfig`` — nothing to configure, and
    nothing registered for it. Its commands need a console, hence the hard requirement.
    """
