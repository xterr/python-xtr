"""A user that knows when another user is the same as it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["EquatableInterface"]


@runtime_checkable
class EquatableInterface(Protocol):
    """A user that decides for itself whether another user is the same.

    Object identity is not enough: a user loaded twice is two objects standing
    for one account. A user implementing this says when another is equal on the
    terms that matter to it — the identifier, and whatever else changing would
    make it a different account.
    """

    def is_equal_to(self, user: UserInterface) -> bool:
        """Tell whether ``user`` is the same as this one."""
        ...
