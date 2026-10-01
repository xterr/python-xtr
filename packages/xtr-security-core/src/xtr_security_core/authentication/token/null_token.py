"""The token that stands for nobody."""

from __future__ import annotations

from typing import final

from .abstract_token import AbstractToken

__all__ = ["NullToken"]


@final
class NullToken(AbstractToken):
    """A token carrying no user and no roles: the anonymous caller.

    An access decision is always made against a token; when authentication
    settled on nobody, it is made against this one. It reports no user, no
    identifier and no roles, so a voter reading roles simply finds none.
    """

    def __init__(self) -> None:
        """Build the token that stands for nobody."""
        super().__init__(user=None, roles=())
