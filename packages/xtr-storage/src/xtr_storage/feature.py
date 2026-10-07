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

    Visibility is the only capability named this way. A checksum, a public url
    and a temporary url each refuse with their own error — respectively
    :class:`~xtr_storage.exception.ChecksumAlgorithmNotSupportedError`,
    :class:`~xtr_storage.exception.UnableToGeneratePublicUrlError` and
    :class:`~xtr_storage.exception.UnableToGenerateTemporaryUrlError` — so there
    is nothing for them to name here.
    """

    VISIBILITY = "visibility"
