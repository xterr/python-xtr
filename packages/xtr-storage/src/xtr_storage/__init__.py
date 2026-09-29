"""Files on local disk, in memory or in object stores, behind one async interface.

A ``Storage`` wraps one adapter and turns paths into reads, writes, listings,
copies and moves. The adapter decides where the bytes live — a directory on this
machine, a dictionary in this process, a bucket on an object store — so code that
stores files is written once and moved between them by its constructor.

Every call that touches a backend is awaited.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("xtr-storage")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = ["__version__"]
