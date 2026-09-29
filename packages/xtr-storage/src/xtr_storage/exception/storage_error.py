"""The root every error in this library derives from."""

from __future__ import annotations

__all__ = ["StorageError"]


class StorageError(Exception):
    """Base class for every error raised by this library.

    Catch this to handle anything storing a file can go wrong with; catch a
    subclass to handle one cause. Every subclass carries the data a caller
    needs as typed attributes and composes its own message from them, so
    nothing has to be parsed back out of a string.

    A message is built from paths and from the reason the backend gave. It
    never carries a key, a token or a connection string: an error travels into
    logs and responses, and credentials must not travel with it.
    """
