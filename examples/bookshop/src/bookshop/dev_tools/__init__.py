"""Development tools, contributed by a bundle active only in dev and test.

The application's scan excludes this package (see ``bookshop.kernel``); ``DevToolsBundle``
names it as its ``resources``, so its commands exist exactly where the bundle is active.
"""

from __future__ import annotations

from .dev_tools_bundle import DevToolsBundle

__all__ = ["DevToolsBundle"]
