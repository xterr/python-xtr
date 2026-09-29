"""What a listing does with a symbolic link it meets."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["LinkHandling"]


class LinkHandling(StrEnum):
    """What a listing does with a symbolic link it meets.

    A link may point anywhere, including outside the directory a storage is
    rooted in, so following one would hand out a file that storage never held.
    Neither answer is right for everyone — a deployment that plants links on
    purpose wants them left out quietly, one that plants none wants to hear
    about the first — so the adapter is told which to give.

    Attributes:
        SKIP: Leave links out of the listing.
        DISALLOW: Raise on the first one met.
    """

    SKIP = "skip"
    DISALLOW = "disallow"
