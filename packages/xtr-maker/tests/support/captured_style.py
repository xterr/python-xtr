"""A console style writing into a buffer the test reads."""

from __future__ import annotations

from io import StringIO
from typing import final

from xtr_console import ConsoleStyle

__all__ = ["CapturedStyle"]


@final
class CapturedStyle:
    """A plain, wide :class:`ConsoleStyle` and what it wrote."""

    def __init__(self) -> None:
        self.buffer = StringIO()
        self.io = ConsoleStyle(self.buffer, StringIO(), width=200, decorated=False)

    @property
    def lines(self) -> list[str]:
        return [line.strip() for line in self.buffer.getvalue().splitlines() if line.strip()]
