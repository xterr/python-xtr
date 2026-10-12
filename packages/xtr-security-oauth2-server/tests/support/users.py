"""A user of the security family, for the bundle layer's events and converters.

The events and converters here take whatever the family's firewall resolved,
and the family ships no concrete user for a library to reuse. This is the
smallest thing that satisfies its contract, so a test about an event's payload
is not also a test about somebody's user class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["SecurityUser"]


@final
class SecurityUser:
    """A user named by its identifier, holding the roles it was given."""

    __slots__ = ("_identifier", "_roles")

    def __init__(self, identifier: str = "user-1", roles: Sequence[str] = ("ROLE_USER",)) -> None:
        self._identifier = identifier
        self._roles = tuple(roles)

    def get_roles(self) -> Sequence[str]:
        return self._roles

    def get_user_identifier(self) -> str:
        return self._identifier
