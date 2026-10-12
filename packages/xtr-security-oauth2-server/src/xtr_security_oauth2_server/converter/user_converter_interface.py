"""What turns the user a firewall resolved into the one a token names."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_oauth2_server.entities.user_entity_interface import UserEntityInterface

__all__ = ["UserConverterInterface"]


@runtime_checkable
class UserConverterInterface(Protocol):
    """Turns a user of the security family into the resource owner of a token.

    One direction only, and deliberately. Going the other way would mean
    loading a user from an identifier, which is a user provider's job and
    already belongs to the family; what is needed here is the narrowing — a
    user with roles, attributes and a password hash becoming the one thing the
    protocol writes into a token.

    An application whose token subject is not the user's own identifier —
    an opaque pairwise identifier, say — replaces this and nothing else.
    """

    def to_entity(self, user: UserInterface) -> UserEntityInterface:
        """Return the resource owner ``user`` is, as the protocol names it."""
        ...
