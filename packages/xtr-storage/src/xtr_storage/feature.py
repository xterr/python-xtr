"""Things a storage can do that not every backend offers."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Feature"]


class Feature(StrEnum):
    """A capability an adapter either has or does not.

    An adapter that cannot do one of these raises
    :class:`~xtr_storage.exception.FeatureNotSupportedError` naming it, rather
    than failing the operation: the difference is between "this backend never
    does that" and "that attempt failed", and only the first is worth changing
    the configuration over.
    """

    VISIBILITY = "visibility"
    CHECKSUM = "checksum"
    PUBLIC_URL = "public_url"
    TEMPORARY_URL = "temporary_url"
