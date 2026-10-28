"""The private registry the security-http command declares into.

Kept out of the process-wide registry a container-less application reads: the
bundle finds this command by the marker :func:`~xtr_console.as_command` leaves
on the class and registers it when it loads the module, so nothing needs to
read this registry — it only stops the declaration leaking into the default
one.
"""

from __future__ import annotations

from xtr_console import CommandsLocator

__all__ = ["SECURITY_HTTP_COMMANDS"]

SECURITY_HTTP_COMMANDS = CommandsLocator()
