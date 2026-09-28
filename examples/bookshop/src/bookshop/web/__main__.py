"""The web entry point: ``uv run bookshop-web`` or ``python -m bookshop.web``.

The environment is loaded before anything reads it, then the server runs the application on
``WEB_HOST`` / ``WEB_PORT``. Stop it with Ctrl-C or SIGTERM: the server stops accepting, the
application's lifespan ends, and the kernel goes down with it — ``@on_shutdown`` hooks, bundles
in reverse, the container's cleanup.
"""

from __future__ import annotations

import os
from typing import Final

import uvicorn

from bookshop.kernel import load_environment

from .app import app

_HOST: Final = "127.0.0.1"
_PORT: Final = 8080


def main() -> None:
    """Load the environment, then serve the application where the variables say."""
    load_environment()
    uvicorn.run(
        app,
        host=os.environ.get("WEB_HOST", _HOST),
        port=int(os.environ.get("WEB_PORT", str(_PORT))),
    )


if __name__ == "__main__":
    main()
