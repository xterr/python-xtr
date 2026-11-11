"""The registry keeping these commands out of the process-wide one."""

from __future__ import annotations

from typing import Final

from xtr_console import CommandsLocator

__all__ = ["AI_COMMANDS"]

AI_COMMANDS: Final = CommandsLocator()
"""The console bundle finds the commands on their classes; this only keeps them registered once."""
