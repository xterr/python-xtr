"""Every error this library raises.

All of them derive from :class:`MakerError`, so one ``except`` catches anything
that can stop a maker, and a narrower one handles one cause. Each carries the
data a caller needs as typed attributes rather than forcing a message to be
parsed.
"""

from __future__ import annotations

from .app_package_not_found_error import AppPackageNotFoundError
from .generated_source_error import GeneratedSourceError
from .invalid_argument_error import InvalidArgumentError
from .invalid_class_name_error import InvalidClassNameError
from .maker_error import MakerError
from .target_exists_error import TargetExistsError
from .unsafe_path_error import UnsafePathError

__all__ = [
    "AppPackageNotFoundError",
    "GeneratedSourceError",
    "InvalidArgumentError",
    "InvalidClassNameError",
    "MakerError",
    "TargetExistsError",
    "UnsafePathError",
]
