"""The console entry point: ``uv run bookshop <command>`` or ``python -m bookshop <command>``.

``*.__main__`` modules are in ``DEFAULT_EXCLUDES``: the scan never imports this file, so it
never runs the application by accident.
"""

from __future__ import annotations

from xtr_console import use_environment_options
from xtr_console.bundle import console

from bookshop.kernel import kernel, load_environment


def main() -> None:
    """Read ``--env``, load the environment, then boot, run the console, shut down, exit.

    ``use_environment_options`` comes first: ``--env`` picks the ``.env.<env>`` files the
    environment loads, and the kernel built after it.
    ``console`` is ``async def console(application: Injected[Application]) -> int``: the
    kernel fills its parameter and runs it between boot and shutdown.
    """
    use_environment_options()
    load_environment()
    raise SystemExit(kernel.run(console))


if __name__ == "__main__":
    main()
