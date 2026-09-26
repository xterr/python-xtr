"""The console's own surface: every ``ConsoleStyle`` method, every declaration shape.

- ``ping`` — ``@as_command`` bare: named after the function; a *sync* command.
- ``demo:echo`` — collected ``*words`` arguments, a counted option, a renamed option.
- ``demo:style`` — ``hidden=True``: runs, but is not listed; every output method and
  question, and every way to end a run.
"""

from __future__ import annotations

import sys
from typing import Annotated, Literal

from xtr_console import ConsoleStyle, ExitCode, Option, Verbosity, as_command, escape

__all__ = ["demo_style", "echo", "ping"]


@as_command
def ping(io: ConsoleStyle) -> int:
    """Answer pong — a sync command runs on the application's event loop too."""
    io.text("pong", verbosity=Verbosity.QUIET)
    return ExitCode.SUCCESS


@as_command("demo:echo")
def echo(
    io: ConsoleStyle,
    *words: str,
    shout: Annotated[int, Option(alias="-s", count=True)] = 0,
    separator: Annotated[str, Option(name="--sep")] = " ",
) -> int:
    """Print the words back.

    Args:
        io: Where the command writes.
        words: Any number of words (collected arguments).
        shout: ``-s`` upper-cases; ``-ss`` adds an exclamation mark (a counted option).
        separator: What joins the words (``--sep``, not ``--separator``).
    """
    text = separator.join(words)
    if shout:
        text = text.upper()
    if shout > 1:
        text += "!"
    io.text(escape(text), verbosity=Verbosity.QUIET)
    return ExitCode.SUCCESS


@as_command("demo:style", hidden=True)
async def demo_style(
    io: ConsoleStyle,
    *,
    ask: bool = False,
    end: Literal["success", "failure", "invalid", "custom", "exit", "raise"] = "success",
) -> int:
    """Every ``ConsoleStyle`` method, and every way a run ends.

    Args:
        io: Where the command writes.
        ask: Ask the questions (``-n`` answers each with its default).
        end: How the run ends: an ``ExitCode``, a custom code (3), ``sys.exit(4)``, or an
            exception — reported as ``[ERROR]`` with ``catch_exceptions``, with its
            traceback at ``-v``.
    """
    io.title("Output")
    io.section("Blocks")
    io.success("success()")
    io.error("error()")
    io.warning("warning()")
    io.caution("caution()")
    io.note("note()")
    io.info("info()")
    io.section("Text at each verbosity")
    for level in (Verbosity.QUIET, Verbosity.NORMAL, Verbosity.VERBOSE, Verbosity.DEBUG):
        io.text(f"shown at {level.name} and above", verbosity=level)
    io.table(
        ["Question", "Answer"],
        [
            ["is_silent()", str(io.is_silent())],
            ["is_quiet()", str(io.is_quiet())],
            ["is_verbose()", str(io.is_verbose())],
            ["is_very_verbose()", str(io.is_very_verbose())],
            ["is_debug()", str(io.is_debug())],
            ["interactive", str(io.interactive)],
            ["decorated", str(io.decorated)],
        ],
    )
    io.listing(["listing()", "[bold]markup[/bold] works", escape("list[int] escaped")])
    io.newline()
    total = 0
    for step in io.progress(range(5), total=5, description="progress()"):
        total += step
    io.text(f"progress() summed {total}")
    if ask:
        io.section("Questions")
        name = io.ask("Name?", "Ada")
        role = io.ask("Role?", "reader", choices=["reader", "staff"])
        secret = io.ask_hidden("Secret?")
        agreed = io.confirm("Proceed?", default=True)
        io.text(f"{escape(name)} / {role} / {'*' * len(secret)} / {agreed}")
    return _end(end)


def _end(end: str) -> int:
    codes = {"success": ExitCode.SUCCESS, "failure": ExitCode.FAILURE, "invalid": ExitCode.INVALID}
    if end in codes:
        return codes[end]
    if end == "custom":
        return 3
    if end == "exit":
        sys.exit(4)
    raise RuntimeError("demo:style was asked to raise")
