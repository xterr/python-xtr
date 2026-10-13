"""The placeholder provider of a firewall that needs one but has none."""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn, final

from typing_extensions import override

from xtr_security_core.exception import BadMethodCallError, InvalidArgumentError

from .user_provider_interface import UserProviderInterface

if TYPE_CHECKING:
    from .user_interface import UserInterface

__all__ = ["MissingUserProvider"]


@final
class MissingUserProvider(UserProviderInterface):
    """Stands where a firewall's user provider should be, when none was defined.

    Building it raises an error naming the firewall, so a firewall whose
    authentication needs a provider fails — with a message saying why — the
    first time that provider is asked for, while a firewall that never needs
    one is unaffected. No instance ever exists, so its methods are never run.
    """

    __slots__ = ()

    def __init__(self, firewall: str) -> None:
        """Refuse to build, naming the firewall missing a provider.

        Raises:
            InvalidArgumentError: Always.
        """
        raise InvalidArgumentError(
            f'"{firewall}" firewall requires a user provider but none was defined.',
        )

    @override
    async def load_user_by_identifier(self, identifier: str) -> NoReturn:
        """Never load a user.

        Raises:
            BadMethodCallError: Always.
        """
        del identifier
        raise BadMethodCallError

    @override
    async def refresh_user(self, user: UserInterface) -> NoReturn:
        """Never refresh a user.

        Raises:
            BadMethodCallError: Always.
        """
        del user
        raise BadMethodCallError

    @override
    def supports_class(self, user_class: type) -> NoReturn:
        """Never answer.

        Raises:
            BadMethodCallError: Always.
        """
        del user_class
        raise BadMethodCallError
