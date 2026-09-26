"""The kernel recipe every entry point shares, and the environment it is built for.

``Kernel(...)`` does no work: it stores a recipe. ``build()``, ``boot()`` and ``run()`` do the
work, each time afresh — so the console, the web server and the worker build their own
container from the same line.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from xtr_dependency_injection import DEFAULT_EXCLUDES, Kernel, exclude
from xtr_dotenv import Dotenv

__all__ = [
    "DEBUG_KEY",
    "ENV_KEY",
    "EXCLUDE",
    "PROD_ENVS",
    "PROJECT_DIR",
    "TEST_ENVS",
    "kernel",
    "load_environment",
]

PROJECT_DIR: Final = Path(__file__).resolve().parents[2]
"""``examples/bookshop``: the nearest directory above the package with a ``pyproject.toml``.

The kernel finds the same directory on its own, as ``kernel.project_dir``.
"""

ENV_KEY: Final = "APP_ENV"
DEBUG_KEY: Final = "APP_DEBUG"
TEST_ENVS: Final = ("test",)
PROD_ENVS: Final = ("prod",)

# DEFAULT_EXCLUDES keeps tests, conftest and __main__ modules out of the scan; ``exclude=``
# replaces it, so it is extended rather than restated. Left out as well:
# - bookshop.dev_tools: the resource of DevToolsBundle, scanned only in the environments
#   that bundle is active in;
# - bookshop.diagnostics.broken_*: deliberately broken, built on their own by demo:errors.
EXCLUDE: Final = (*DEFAULT_EXCLUDES, "bookshop.dev_tools", "bookshop.diagnostics.broken_*")

kernel: Final = Kernel(
    "bookshop",
    # env=None      -> the APP_ENV variable, else "dev".
    # debug=None    -> the APP_DEBUG variable, else "not prod".
    # bundles=None  -> bookshop.bundles.BUNDLES.
    # resources=None -> scan the package itself.
    # environ=None  -> read APP_ENV, APP_DEBUG and every env() from os.environ.
    name="bookshop",
    # The only environments this application accepts: anything else is an
    # InvalidEnvironmentError before a single module is imported.
    allowed_envs=("dev", "test", "prod"),
    exclude=EXCLUDE,
)


@exclude
def load_environment() -> None:
    """Load the layered ``.env`` files into ``os.environ`` — before the kernel is built.

    ``@exclude`` keeps this helper out of the scan: it is an entry-point concern, never a
    service candidate. ``boot_env`` reads ``.env.local.json`` (written by ``dotenv:dump``)
    when it applies, else the cascade ``.env`` -> ``.env.local`` -> ``.env.{env}`` ->
    ``.env.{env}.local``; a real environment variable always wins. It then sets APP_DEBUG
    to ``1`` or ``0``.
    """
    _ = (
        Dotenv(env_key=ENV_KEY, debug_key=DEBUG_KEY)
        .set_prod_envs(PROD_ENVS)
        .boot_env(str(PROJECT_DIR / ".env"), default_env="dev", test_envs=TEST_ENVS)
    )
