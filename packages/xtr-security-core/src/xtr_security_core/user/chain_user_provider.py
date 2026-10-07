"""A provider that tries several providers in turn."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_security_core.exception import UnsupportedUserError, UserNotFoundError

from .attributes_based_user_provider_interface import AttributesBasedUserProviderInterface
from .password_upgrader_interface import PasswordUpgraderInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_password_hasher import PasswordAuthenticatedUserInterface

    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

__all__ = ["ChainUserProvider"]


@final
class ChainUserProvider(AttributesBasedUserProviderInterface, PasswordUpgraderInterface):
    """Asks each provider in order, until one answers.

    An application may load users from more than one place — a database and a
    fixed set of service accounts. This tries each provider for an identifier,
    catching the not-found of one and moving to the next, and reports not-found
    only when none answered. When attributes come with the identifier they are
    handed to every provider that reads them, and a password upgrade fans out
    to every provider that can perform one for the user's class.
    """

    __slots__ = ("_providers",)

    _providers: tuple[UserProviderInterface, ...]

    def __init__(self, providers: Sequence[UserProviderInterface]) -> None:
        """Record the providers to try, in order."""
        self._providers = tuple(providers)

    @override
    async def load_user_by_identifier(
        self,
        identifier: str,
        attributes: Mapping[str, object] | None = None,
    ) -> UserInterface:
        """Load ``identifier`` from the first provider that has it.

        A provider that reads attributes is given them; the rest are asked the
        plain way.

        Raises:
            UserNotFoundError: When no provider has the user.
        """
        for provider in self._providers:
            try:
                if _reads_attributes(provider):
                    attributed = cast("AttributesBasedUserProviderInterface", provider)
                    return await attributed.load_user_by_identifier(identifier, attributes)
                return await provider.load_user_by_identifier(identifier)
            except UserNotFoundError:
                continue
        raise UserNotFoundError(identifier)

    @override
    def supports_class(self, user_class: type) -> bool:
        """Tell whether any chained provider loads ``user_class``."""
        return any(provider.supports_class(user_class) for provider in self._providers)

    @override
    async def upgrade_password(
        self,
        user: PasswordAuthenticatedUserInterface,
        new_hashed_password: str,
    ) -> None:
        """Upgrade ``user``'s stored password wherever a provider can.

        A provider that cannot upgrade, or does not handle the user's class, is
        skipped; the rest are asked, so a user stored in more than one place is
        kept in step. A provider that turns the user away is skipped too.
        """
        user_class = type(user)
        for provider in self._providers:
            if provider.supports_class(user_class) and isinstance(
                provider, PasswordUpgraderInterface
            ):
                with contextlib.suppress(UnsupportedUserError):
                    await provider.upgrade_password(user, new_hashed_password)

    def get_providers(self) -> Sequence[UserProviderInterface]:
        """Return the chained providers, in order."""
        return self._providers


def _reads_attributes(provider: UserProviderInterface) -> bool:
    """Tell, nominally, whether ``provider`` declares itself attributes-based.

    A structural check cannot help here: the attributes-based contract adds
    only an optional parameter to a method the plain contract already has, so
    every provider matches it by shape. Membership in the class's resolution
    order asks the reliable question — did this provider *say* it reads
    attributes — so a plain provider is never handed a parameter it cannot take.
    """
    return AttributesBasedUserProviderInterface in type(provider).__mro__
