"""An adapter was asked for something its backend does not do."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .storage_error import StorageError

if TYPE_CHECKING:
    from xtr_storage.feature import Feature

__all__ = ["FeatureNotSupportedError"]


class FeatureNotSupportedError(StorageError, NotImplementedError):
    """The backend behind this adapter has no such capability.

    Kept apart from every operation failure on purpose: a failed operation may
    work next time, this one never will. It says "configure something else",
    not "try again" — so a retry loop catching operation failures leaves it
    alone, and a caller that can do without the capability catches this one
    class and goes on.

    Also a :class:`NotImplementedError`, which is what an implementation that
    does not implement something raises.

    Attributes:
        feature: The capability that is missing.
        adapter: The name of the adapter class that does not have it.
    """

    feature: Feature
    adapter: str

    def __init__(self, feature: Feature, adapter: str) -> None:
        """Record which capability is missing from which adapter."""
        self.feature = feature
        self.adapter = adapter
        super().__init__(f"{adapter} does not support {feature}")
