"""A badge marking a user pre-authenticated, needing no credential check."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from .badge_interface import BadgeInterface

__all__ = ["PreAuthenticatedUserBadge"]


@final
class PreAuthenticatedUserBadge(BadgeInterface):
    """States that the user was already authenticated elsewhere.

    A bearer token was verified by its handler before ever reaching a
    passport; there are no credentials on the passport to check. This badge
    stands for that fact — it is resolved from the moment it exists, so the
    credentials listener knows there is nothing to verify.
    """

    @override
    def is_resolved(self) -> bool:
        """Report resolved always: a pre-authenticated user needs no check."""
        return True
