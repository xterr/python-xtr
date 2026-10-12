"""The private registry this package's console commands declare into.

Kept out of the process-wide registry a container-less application reads: the
bundle finds these commands by the marker :func:`~xtr_console.as_command`
leaves on the class and registers each module it loads, so nothing needs to
read this registry — it only stops the declarations leaking into the default
one.
"""

from __future__ import annotations

from xtr_console import CommandsLocator

__all__ = ["OAUTH2_SERVER_COMMANDS"]

OAUTH2_SERVER_COMMANDS = CommandsLocator()
