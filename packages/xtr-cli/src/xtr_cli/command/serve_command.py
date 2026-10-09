"""``server:start``: serve the application the current directory belongs to."""

from __future__ import annotations

import shlex
from pathlib import Path  # noqa: TC003 — the console reads annotations at runtime.
from typing import TYPE_CHECKING, Annotated, final

from xtr_console import ConsoleStyle, ExitCode, Option, Range, as_command, escape

from xtr_cli import command_support
from xtr_cli.exception import AmbiguousWebEntryPointError, CliError, WebEntryPointNotFoundError
from xtr_cli.subprocess_runner import NOT_FOUND
from xtr_cli.web_entry_point_finder import WebEntryPointFinder

if TYPE_CHECKING:
    from xtr_cli.web_entry_point import WebEntryPoint

__all__ = ["ServeCommand"]

_NONE_FOUND = (
    "no console script imports a server or is named *-web, and no module defines a "
    "FastAPI(), Starlette() or Litestar() application; pass --entrypoint"
)


@as_command("server:start", aliases="serve")
@final
class ServeCommand:
    """Serve the application the current directory belongs to.

    The web entry point is found in the project — its web console script, or
    else a module-level ASGI application — and run in the project's own
    environment with ``uv run``. The server restarts on every source change
    unless ``--no-reload`` is given. Ctrl-C stops the server, and waits for the
    application to shut down.
    """

    async def __call__(  # noqa: PLR0913 — one parameter per option.
        self,
        io: ConsoleStyle,
        *,
        project_dir: Path | None = None,
        entrypoint: str | None = None,
        host: str | None = None,
        port: Annotated[
            int | None,
            Option(
                validator=Range(gte=1, lte=65535),
                help="The port to listen on; the entry point's own default when left out.",
            ),
        ] = None,
        reload: Annotated[
            bool,
            Option(
                negative="--no-reload",
                help="Restart the server when a source file changes; --no-reload turns it off.",
            ),
        ] = True,
        dry_run: bool = False,
    ) -> int:
        """Serve the application the current directory belongs to.

        Args:
            io: Where the choice is asked and the command reported.
            project_dir: The project to serve; the nearest one at or above the
                current directory by default.
            entrypoint: What to serve: a console script, or a module:attribute
                ASGI application. Found in the project when left out.
            host: Where to listen; the entry point's own default when left out.
            port: The port to listen on.
            reload: Restart the server when a source file changes; on by default,
                --no-reload turns it off.
            dry_run: Print the command, and run nothing.

        Returns:
            The server's exit code, or a failure when there is nothing to serve.
        """
        finder = WebEntryPointFinder()
        try:
            directory = finder.project_dir(project_dir)
            chosen = (
                finder.resolve(directory, entrypoint)
                if entrypoint is not None
                else _choose(io, finder.find(directory), directory)
            )
        except CliError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        argv, environment = chosen.command(host, port, reload=reload)
        assignments = [f"{key}={shlex.quote(value)}" for key, value in environment.items()]
        io.text(escape(f"Serving {chosen.label} from {directory}"))
        io.text(escape("  " + " ".join((*assignments, shlex.join(argv)))))
        if dry_run:
            return ExitCode.SUCCESS
        code = command_support.build_runner().run(argv, directory, environment)
        if code == NOT_FOUND:
            io.error("uv is not on the PATH: install it from https://docs.astral.sh/uv/")
        return code


def _choose(
    io: ConsoleStyle, candidates: tuple[WebEntryPoint, ...], directory: Path
) -> WebEntryPoint:
    """Return the one candidate, or the one picked; with no question possible, refuse."""
    if not candidates:
        raise WebEntryPointNotFoundError(directory, _NONE_FOUND)
    if len(candidates) == 1:
        return candidates[0]
    labels = tuple(candidate.label for candidate in candidates)
    if not io.interactive:
        raise AmbiguousWebEntryPointError(labels)
    picked = io.ask("Web entry point", labels[0], choices=labels)
    return candidates[labels.index(picked)]
