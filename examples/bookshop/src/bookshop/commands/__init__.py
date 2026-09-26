"""The application's console commands, found by the kernel's scan.

A command module imports nothing from the console bundle: ``@as_command`` marks the
function or class, and the console bundle's autoconfiguration registers every one the scan
finds into this kernel's ``CommandsLocator``. A parameter is filled by one of three parties:

=============================  ==================================================
Parameter                      Filled by
=============================  ==================================================
annotated ``ConsoleStyle``     the application — where the command writes
``Injected[T]`` / ``Autowire``  the container, in a scope of its own per run
anything else                  the command line: before a bare ``*`` an argument,
                               after it an option
=============================  ==================================================

A class command's *constructor* is injected like any service (``Target`` included); its
``__call__`` follows the table above.
"""

from __future__ import annotations

__all__: list[str] = []
