"""Resolving which hasher a user, class or name is hashed by."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_password_hasher.exception import UnknownPasswordHasherError

from .password_hasher_aware_interface import PasswordHasherAwareInterface
from .password_hasher_factory_interface import PasswordHasherFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_password_hasher.password_authenticated_user_interface import (
        PasswordAuthenticatedUserInterface,
    )
    from xtr_password_hasher.password_hasher_interface import PasswordHasherInterface

    _User = str | type | PasswordAuthenticatedUserInterface | PasswordHasherAwareInterface

__all__ = ["PasswordHasherFactory"]


@final
class PasswordHasherFactory(PasswordHasherFactoryInterface):
    """Hands out a hasher per user, chosen from a mapping keyed by class or name.

    A key is a user class, a ``"module:Class"`` string, or a name a user
    declares through
    :class:`~xtr_password_hasher.PasswordHasherAwareInterface`. Resolution, in
    order:

    1. a user that declares a hasher name is looked up by that name;
    2. otherwise the user's class — the class itself, or ``type(user)`` — is
       walked up its ``__mro__``, matching a class key or the matching
       ``"module:Class"`` string at each step;
    3. a bare name or ``"module:Class"`` string passed in is looked up as it is.

    A mapping value is a ready hasher. Turning inert configuration into a live
    hasher — argon2 costs, migrating chains, a hasher a container provides — is
    the caller's job, so the factory carries no configuration vocabulary and
    hashes standalone from the same instances a bundle would build.
    """

    __slots__ = ("_hashers",)

    def __init__(
        self,
        password_hashers: Mapping[type | str, PasswordHasherInterface],
    ) -> None:
        """Resolve users against ``password_hashers``, keyed by class or name."""
        self._hashers = dict(password_hashers)

    @override
    def get_password_hasher(self, user: _User) -> PasswordHasherInterface:
        """Return the hasher for ``user``.

        Raises:
            UnknownPasswordHasherError: When nothing is configured for it.
        """
        key = self._resolve_key(user)
        if key is None:
            raise UnknownPasswordHasherError(_describe(user))
        return self._hashers[key]

    def _resolve_key(self, user: _User) -> type | str | None:
        if isinstance(user, str):
            return user if user in self._hashers else None
        if isinstance(user, type):
            return self._resolve_class(user)
        if isinstance(user, PasswordHasherAwareInterface):
            name = user.get_password_hasher_name()
            if name is not None:
                return name if name in self._hashers else None
        return self._resolve_class(type(user))

    def _resolve_class(self, cls: type) -> type | str | None:
        for base in cls.__mro__:
            if base in self._hashers:
                return base
            label = f"{base.__module__}:{base.__qualname__}"
            if label in self._hashers:
                return label
        return None


def _describe(user: _User) -> str:
    if isinstance(user, str):
        return user
    cls = user if isinstance(user, type) else type(user)
    return f"{cls.__module__}:{cls.__qualname__}"
