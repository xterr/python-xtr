"""The console entry point: ``uv run bookshop <command>`` or ``python -m bookshop <command>``.

``*.__main__`` modules are in ``DEFAULT_EXCLUDES``: the scan never imports this file, so it
never runs the application by accident.
"""

from __future__ import annotations

from xtr_console.bundle import console

from bookshop.kernel import kernel, load_environment


def main() -> None:
    """Load the environment, then boot, run the console, shut down, exit with its code.

    ``console`` is ``async def console(application: Injected[Application]) -> int``: the
    kernel fills its parameter and runs it between boot and shutdown.
    """
    load_environment()
    raise SystemExit(kernel.run(console))


if __name__ == "__main__":
    main()
