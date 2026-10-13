"""What loads a user by the identifier authentication resolved."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["UserProviderInterface"]


@runtime_checkable
class UserProviderInterface(Protocol):
    """Loads a user given the identifier authentication established.

    Authentication proves who is calling — a username, a token's ``sub`` — and
    then asks a provider to turn that identifier into a user object the rest of
    the library reasons about. A provider works with one class of user;
    :meth:`supports_class` says which, and :meth:`refresh_user` reloads a user
    of that class held from an earlier unit of work.
    """

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        """Refresh ``user``.

        It is up to the implementation to decide whether the user data is
        reloaded entirely — from the database, say — or whether the user
        object can just be merged into an identity map it keeps.

        Raises:
            UnsupportedUserError: When the user is not of a class this provider
                supports.
            UserNotFoundError: When the user is not found.
        """
        ...

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        """Load the user named by ``identifier``.

        Raises:
            UserNotFoundError: When no user matches ``identifier``.
        """
        ...

    def supports_class(self, user_class: type) -> bool:
        """Tell whether this provider loads users of ``user_class``."""
        ...
