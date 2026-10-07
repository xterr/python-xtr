"""What an operation does with a symbolic link it meets."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["LinkHandling"]


class LinkHandling(StrEnum):
    """What an operation does with a symbolic link it meets.

    A link may point anywhere, including outside the directory a storage is
    rooted in, so following one would hand out a file that storage never held.
    Neither answer is right for everyone — a deployment that plants links on
    purpose wants them left out quietly, one that plants none wants to hear
    about the first — so the adapter is told which to give.

    Both answers keep the storage inside its root. This setting decides what a
    *listing* does with a link; neither value makes the tree above the root
    reachable through one, so a read, a write or a delete naming a path a link
    carries outside the root is refused either way.

    Attributes:
        SKIP: Leave links out of the listing. A link is hidden, not a door: one
            that resolves outside the root is still refused on a direct
            operation.
        DISALLOW: Raise on the first one met.
    """

    SKIP = "skip"
    DISALLOW = "disallow"
