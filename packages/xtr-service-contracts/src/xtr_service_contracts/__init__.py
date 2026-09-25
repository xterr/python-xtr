"""Contracts for the lifecycle of a service: what a container drives, not what a service does.

A service's own contract says what it is for — a logger logs, a lock locks. This
package holds the other kind: what something built by a container must answer to
so the container can manage it, whatever it is for.

Deliberately a leaf. It has no dependencies and should never acquire any, because
every other contract package in this ecosystem is free to depend on this one, and
that only stays true while nothing here can drag anything in.
"""

from importlib.metadata import PackageNotFoundError, version

from .resettable_interface import ResettableInterface

try:
    __version__ = version("xtr-service-contracts")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "ResettableInterface",
    "__version__",
]
