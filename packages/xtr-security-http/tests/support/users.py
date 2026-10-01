"""Users and credential checks for the HTTP-edge tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core.user.in_memory_user import InMemoryUser

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


def accept(value: object, user: object) -> bool:
    """A credential check that always passes."""
    del value, user
    return True


def reject(value: object, user: object) -> bool:
    """A credential check that always fails."""
    del value, user
    return False


def loader(
    *,
    roles: Sequence[str] = ("ROLE_USER",),
    password: str | None = None,
    enabled: bool = True,
) -> Callable[[str], InMemoryUser]:
    """Return a user loader building an in-memory user with the given fields."""

    def load(identifier: str) -> InMemoryUser:
        return InMemoryUser(identifier, password=password, roles=roles, enabled=enabled)

    return load
