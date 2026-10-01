"""A provider backed by a fixed set of users held in memory."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_security_core.exception import (
    InvalidArgumentError,
    UnsupportedUserError,
    UserNotFoundError,
)

from .in_memory_user import InMemoryUser
from .user_provider_interface import UserProviderInterface

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

__all__ = ["InMemoryUserProvider"]


@final
class InMemoryUserProvider(UserProviderInterface):
    """Loads users from a set defined up front, not from a store.

    Built either from ready :class:`InMemoryUser` objects or from a mapping of
    identifier to the fields one is made of — ``{"alice": {"password": ...,
    "roles": (...), "enabled": True}}`` — so a small fixed set of accounts is
    a few lines of configuration.
    """

    __slots__ = ("_users",)

    def __init__(
        self,
        users: Mapping[str, InMemoryUser | Mapping[str, object]] | None = None,
    ) -> None:
        """Build the provider from ready users or from their fields."""
        self._users: dict[str, InMemoryUser] = {}
        for identifier, definition in (users or {}).items():
            self.add_user(self._coerce(identifier, definition))

    def add_user(self, user: InMemoryUser) -> None:
        """Add ``user`` to the set, replacing any user with its identifier."""
        self._users[user.get_user_identifier()] = user

    @override
    async def load_user_by_identifier(self, identifier: str) -> InMemoryUser:
        """Load the user named by ``identifier``.

        Raises:
            UserNotFoundError: When no user matches ``identifier``.
        """
        user = self._users.get(identifier)
        if user is None:
            raise UserNotFoundError(identifier)
        return user

    @override
    def supports_class(self, user_class: type) -> bool:
        """Tell whether ``user_class`` is the in-memory user."""
        return issubclass(user_class, InMemoryUser)

    @staticmethod
    def _coerce(identifier: str, definition: InMemoryUser | Mapping[str, object]) -> InMemoryUser:
        """Turn a definition into an :class:`InMemoryUser`, checking its identifier."""
        if isinstance(definition, InMemoryUser):
            found = definition.get_user_identifier()
            if found != identifier:
                raise InvalidArgumentError(
                    f'The user under "{identifier}" has identifier "{found}".',
                )
            return definition
        password = definition.get("password")
        roles = definition.get("roles", ())
        enabled = definition.get("enabled", True)
        if password is not None and not isinstance(password, str):
            raise UnsupportedUserError(f'The password of "{identifier}" must be a string.')
        if not isinstance(enabled, bool):
            raise UnsupportedUserError(f'The enabled flag of "{identifier}" must be a boolean.')
        return InMemoryUser(
            identifier=identifier,
            password=password,
            roles=tuple(_as_str_sequence(roles)),
            enabled=enabled,
        )


def _as_str_sequence(value: object) -> Sequence[str]:
    """Read ``value`` as a sequence of role strings, or reject it."""
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise UnsupportedUserError("Roles must be given as a list or tuple of strings.")
    items = cast("Iterable[object]", value)
    return [str(role) for role in items]
