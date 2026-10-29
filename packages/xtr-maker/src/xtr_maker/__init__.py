"""Console commands that write application code for the xtr libraries.

Every maker writes through the same pieces, usable on their own:

* :class:`~xtr_maker.class_name.ClassName` — what a person typed, as the class,
  module and file under the folder for its kind.
* :class:`~xtr_maker.name_converter.NameConverter` — one name as a class, a
  module, a console name or a table.
* :class:`~xtr_maker.import_collector.ImportCollector` — the imports a module
  needs, grouped and sorted.
* :class:`~xtr_maker.template_renderer.TemplateRenderer` — a template rendered,
  and refused when its Python does not parse.
* :class:`~xtr_maker.file_manager.FileManager` — the application package on
  disk, and writes kept inside the project.
* :class:`~xtr_maker.generator.Generator` — the files of one run, queued, then
  written together.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .class_name import ClassName
from .exception import (
    AppPackageNotFoundError,
    GeneratedSourceError,
    InvalidArgumentError,
    InvalidClassNameError,
    MakerError,
    TargetExistsError,
    UnsafePathError,
)
from .file_manager import FileManager
from .generator import Generator
from .import_collector import ImportCollector
from .name_converter import NameConverter
from .template_renderer import TemplateRenderer

try:
    __version__ = version("xtr-maker")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read.
    __version__ = "0+unknown"

__all__ = [
    "AppPackageNotFoundError",
    "ClassName",
    "FileManager",
    "GeneratedSourceError",
    "Generator",
    "ImportCollector",
    "InvalidArgumentError",
    "InvalidClassNameError",
    "MakerError",
    "NameConverter",
    "TargetExistsError",
    "TemplateRenderer",
    "UnsafePathError",
    "__version__",
]
