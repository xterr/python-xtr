"""A console style writing into a buffer the test reads, answering from scripted lines."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING, final

from xtr_console import ConsoleStyle

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["CapturedStyle"]


@final
class CapturedStyle:
    """A plain, wide :class:`ConsoleStyle` and what it wrote.

    Questions are answered from ``inputs``, one line each, in the order asked;
    once they run out, every question gets its default. ``interactive=False``
    asks nothing, as ``-n`` does.
    """

    def __init__(self, inputs: Sequence[str] = (), *, interactive: bool = True) -> None:
        self.buffer = StringIO()
        self.io = ConsoleStyle(
            self.buffer,
            self.buffer,
            width=200,
            decorated=False,
            input_stream=StringIO("".join(f"{line}\n" for line in inputs)),
            interactive=interactive,
        )

    @property
    def output(self) -> str:
        return self.buffer.getvalue()

    @property
    def lines(self) -> list[str]:
        return [line.strip() for line in self.output.splitlines() if line.strip()]
