"""Every error this library raises.

All of them derive from :class:`CliError`, so one ``except`` catches anything
scaffolding a project can go wrong with, and a narrower one handles a single
cause.
"""

from __future__ import annotations

from .cli_error import CliError
from .directory_not_empty_error import DirectoryNotEmptyError
from .invalid_project_name_error import InvalidProjectNameError
from .invalid_template_error import InvalidTemplateError
from .step_failed_error import StepFailedError
from .unknown_add_on_error import UnknownAddOnError
from .unknown_template_error import UnknownTemplateError
from .unsupported_python_error import UnsupportedPythonError

__all__ = [
    "CliError",
    "DirectoryNotEmptyError",
    "InvalidProjectNameError",
    "InvalidTemplateError",
    "StepFailedError",
    "UnknownAddOnError",
    "UnknownTemplateError",
    "UnsupportedPythonError",
]
