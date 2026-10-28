"""Creates a new application on the xtr packages, ready to run, in one command.

``xtr new <directory>`` asks nothing: it makes a console application, or a web
application with ``--webapp``. It writes the few files no package's recipe can
(the project manifest, the kernel and the entry points), installs the packages
with ``uv``, and lets each package's recipe configure itself with
``xtr-recipes recipes:sync``. The project it leaves boots, and is already in
the state a recipe check expects.

This module exposes the pieces that plan and make a project; the commands that
drive them live in :mod:`xtr_cli.command`, behind the ``xtr`` console script.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .exception import (
    AmbiguousWebEntryPointError,
    CliError,
    DirectoryNotEmptyError,
    InvalidProjectNameError,
    InvalidTemplateError,
    ProjectNotFoundError,
    StepFailedError,
    UnknownTemplateError,
    UnsupportedPythonError,
    WebEntryPointNotFoundError,
)
from .process_runner_interface import ProcessRunnerInterface
from .project_name import ProjectName
from .project_settings import ProjectSettings
from .scaffold_plan import ScaffoldPlan
from .scaffolder import Scaffolder
from .subprocess_runner import SubprocessRunner
from .template import Template
from .template_catalog import TemplateCatalog
from .web_entry_point import WebEntryPoint
from .web_entry_point_finder import WebEntryPointFinder

try:
    __version__ = version("xtr-cli")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read. Having no
    # version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "AmbiguousWebEntryPointError",
    "CliError",
    "DirectoryNotEmptyError",
    "InvalidProjectNameError",
    "InvalidTemplateError",
    "ProcessRunnerInterface",
    "ProjectName",
    "ProjectNotFoundError",
    "ProjectSettings",
    "ScaffoldPlan",
    "Scaffolder",
    "StepFailedError",
    "SubprocessRunner",
    "Template",
    "TemplateCatalog",
    "UnknownTemplateError",
    "UnsupportedPythonError",
    "WebEntryPoint",
    "WebEntryPointFinder",
    "WebEntryPointNotFoundError",
    "__version__",
]
