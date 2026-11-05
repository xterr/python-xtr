"""The kernel recipe every entry point shares, and the environment it is built for.

``Kernel(...)`` does no work: it stores a recipe. ``build()``, ``boot()`` and ``run()`` do the
work, each time afresh — so the console, the web server and the worker build their own
container from the same line. ``Kernel(__package__)`` names the application package once, here
inside it, where it cannot drift from the package's real name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from xtr_dependency_injection import Kernel, exclude

from bookshop.config.packages.dotenv import DOTENV

__all__ = [
    "EXCLUDE",
    "PROJECT_DIR",
    "kernel",
    "load_environment",
]

PROJECT_DIR: Final = Path(__file__).resolve().parents[2]
"""``examples/bookshop``: the nearest directory above the package with a ``pyproject.toml``.

The kernel finds the same directory on its own, as ``kernel.project_dir``.
"""

# DEFAULT_EXCLUDES keeps tests, conftest and __main__ modules out of the scan, and ``exclude=``
# adds to it; a pattern starting with "." is relative to this package. Left out as well:
# - bookshop.dev_tools: the resource of DevToolsBundle, scanned only in the environments
#   that bundle is active in;
# - bookshop.diagnostics.broken_*: deliberately broken, built on their own by demo:errors.
# - bookshop.web.app: it builds the web application as it is imported, and that application
#   is served from this very kernel — scanning it would import it while the kernel builds.
EXCLUDE: Final = (".dev_tools", ".diagnostics.broken_*", ".web.app")

kernel: Final = Kernel(
    __package__,
    # env=None      -> the APP_ENV variable, else "dev".
    # debug=None    -> the APP_DEBUG variable, else "not prod".
    # bundles=None  -> bookshop.config.bundles.BUNDLES.
    # environ=None  -> read APP_ENV, APP_DEBUG and every env() from os.environ.
    # name=None     -> the package's own name, "bookshop".
    # The only environments this application accepts: anything else is an
    # InvalidEnvironmentError before a single module is imported. They are also the only names
    # a folder under config/packages/ or config/routes/ may take: config/packages/dev/ is
    # imported in dev alone, after the common modules, and never in prod.
    allowed_envs=("dev", "test", "prod"),
    exclude=EXCLUDE,
)


@exclude
def load_environment() -> None:
    """Boot the layered ``.env`` files into ``os.environ`` — before the kernel is built.

    ``@exclude`` keeps this helper out of the scan: it is an entry-point concern, never a
    service candidate. ``DOTENV`` — the one description, in ``config/packages/dotenv.py`` —
    builds the loader and resolves the base path, so the entry point and the
    ``dotenv:dump`` / ``debug:dotenv`` commands run the very same cascade:
    ``.env.local.json`` (written by ``dotenv:dump``) when it applies and was compiled from
    that same description, else ``.env`` -> ``.env.local`` -> ``.env.{env}`` ->
    ``.env.{env}.local``; a real environment variable always wins. It then sets APP_DEBUG
    to ``1`` or ``0`` — on by default only in the environments ``DOTENV.debug_envs``
    declares.
    """
    _ = DOTENV.boot(PROJECT_DIR)
