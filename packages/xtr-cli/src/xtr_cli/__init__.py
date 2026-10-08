"""Creates a new application on the xtr packages, ready to run, in one command.

``xtr new <directory>`` asks for what it was not told — the template, the
add-ons — writes the few files no package's recipe can (the project manifest,
the kernel and the entry points), installs the packages with ``uv``, and lets
each package's recipe configure itself with ``xtr-recipes recipes:sync``. The
project it leaves boots, and is already in the state a recipe check expects.

This module exposes the pieces that plan and make a project; the commands that
drive them live in :mod:`xtr_cli.command`, behind the ``xtr`` console script.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .add_on import AddOn
from .add_on_catalog import AddOnCatalog
from .add_on_choice import AddOnChoice
from .exception import (
    CliError,
    DirectoryNotEmptyError,
    InvalidProjectNameError,
    InvalidTemplateError,
    StepFailedError,
    UnknownAddOnError,
    UnknownTemplateError,
    UnsupportedPythonError,
)
from .process_runner_interface import ProcessRunnerInterface
from .project_name import ProjectName
from .project_questions import ProjectQuestions
from .project_settings import ProjectSettings
from .scaffold_plan import ScaffoldPlan
from .scaffolder import Scaffolder
from .subprocess_runner import SubprocessRunner
from .template import Template
from .template_catalog import TemplateCatalog

try:
    __version__ = version("xtr-cli")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read. Having no
    # version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "AddOn",
    "AddOnCatalog",
    "AddOnChoice",
    "CliError",
    "DirectoryNotEmptyError",
    "InvalidProjectNameError",
    "InvalidTemplateError",
    "ProcessRunnerInterface",
    "ProjectName",
    "ProjectQuestions",
    "ProjectSettings",
    "ScaffoldPlan",
    "Scaffolder",
    "StepFailedError",
    "SubprocessRunner",
    "Template",
    "TemplateCatalog",
    "UnknownAddOnError",
    "UnknownTemplateError",
    "UnsupportedPythonError",
    "__version__",
]
