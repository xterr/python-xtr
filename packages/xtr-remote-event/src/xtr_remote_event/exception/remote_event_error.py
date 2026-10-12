"""The error every other error of this package derives from."""

from __future__ import annotations

__all__ = ["RemoteEventError"]


class RemoteEventError(Exception):
    """Something this library could not do — catch this to catch them all.

    Code receiving events from elsewhere is usually on the edge of the
    application, where one ``except`` has to answer the sender. This is that
    one: catch it to turn any failure of this library into a reply, catch a
    subclass to tell a payload that cannot be read from a source nobody
    answers for.
    """
