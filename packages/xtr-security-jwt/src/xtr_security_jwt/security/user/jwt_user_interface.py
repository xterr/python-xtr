"""A user that can be rebuilt from the payload of a token that names it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from xtr_security_core.user.user_interface import UserInterface

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Self

__all__ = ["JwtUserInterface"]


@runtime_checkable
class JwtUserInterface(UserInterface, Protocol):
    """A user a stateless provider builds from a token's own claims.

    A deployment that keeps no user store carries everything about a user inside
    the token, and this rebuilds the user object from those claims — the roles
    and whatever else the class reads — so a request authenticates with no lookup.
    """

    @classmethod
    def create_from_payload(cls, username: str, payload: Mapping[str, object]) -> Self:
        """Build a user named ``username`` from the token's ``payload``."""
        ...
