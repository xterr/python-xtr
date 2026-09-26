"""What a pool stores alongside a value, and reports back about it."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["Metadata"]


class Metadata(TypedDict, total=False):
    """Facts about a cached value, every one of them optional.

    A pool that records none returns an empty mapping. The keys a pool fills
    in are what makes early recomputation possible: knowing when a value
    expires and how long it took to compute is enough to refresh it shortly
    before it runs out, instead of making every caller wait once it has.

    Attributes:
        expiry: When the value expires, as a Unix timestamp in seconds. Wall
            clock rather than monotonic, because the value is shared with
            other processes and other machines.
        ctime: How long the value took to compute, in milliseconds.
        tags: The tags the value was saved with.
        save_failed: Set by :meth:`CacheInterface.get
            <xtr_cache_contracts.cache_interface.CacheInterface.get>` when the
            value it computed could not be saved. Never stored, so never in
            :attr:`ItemInterface.metadata
            <xtr_cache_contracts.item_interface.ItemInterface.metadata>`.
    """

    expiry: float
    ctime: int
    tags: Sequence[str]
    save_failed: bool
