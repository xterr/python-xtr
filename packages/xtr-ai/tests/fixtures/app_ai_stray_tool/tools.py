"""A tool for an agent nobody configured."""

from __future__ import annotations

from xtr_ai import as_tool


class Stray:
    @as_tool(agents=("ghost",))
    def lookup(self) -> str:
        return "boo"
