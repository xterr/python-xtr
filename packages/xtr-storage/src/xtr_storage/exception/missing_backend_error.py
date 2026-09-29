"""An adapter needs a package that is not installed."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["MissingBackendError"]


class MissingBackendError(StorageError, ImportError):  # pyright: ignore[reportUnsafeMultipleInheritance] -- StorageError adds no __init__, so ImportError's is the one the MRO reaches
    """The package this adapter talks to its backend through is not installed.

    Backends live behind extras so an application installs only the ones it
    reaches. An adapter imports its package the first time it is used, and
    turns a failed import into this — an error naming the extra to install,
    rather than a traceback about a module nobody asked for.

    Also an :class:`ImportError`, so it reads as what it is.

    Attributes:
        package: The package that is missing.
        extra: The extra of this distribution that installs it.
    """

    package: str
    extra: str

    def __init__(self, package: str, extra: str) -> None:
        """Record the missing package and the extra that brings it."""
        self.package = package
        self.extra = extra
        super().__init__(
            f'this storage needs the "{package}" package: install "xtr-storage[{extra}]".'
        )
