"""``demo:echo`` — collected ``*words`` arguments, a counted option, a renamed option."""

from __future__ import annotations

from typing import Annotated

from xtr_console import ConsoleStyle, ExitCode, Option, Verbosity, as_command, escape

__all__ = ["echo"]


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
