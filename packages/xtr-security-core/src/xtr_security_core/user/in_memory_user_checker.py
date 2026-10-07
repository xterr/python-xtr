"""A checker that refuses a disabled account."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.exception import DisabledError

from .enabled_aware_interface import EnabledAwareInterface
from .user_checker_interface import UserCheckerInterface

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["InMemoryUserChecker"]


@final
class InMemoryUserChecker(UserCheckerInterface):
    """Refuses a user whose account reports itself disabled.

    Pairs with :class:`~xtr_security_core.user.in_memory_user.InMemoryUser`: a user
    that carries an ``is_enabled`` answering ``False`` is turned away before its
    credentials are ever checked. A user without that method is left alone —
    this checker has nothing to say about it.
    """

    @override
    async def check_pre_auth(self, user: UserInterface) -> None:
        """Refuse ``user`` when its account reports itself disabled.

        Raises:
            DisabledError: When the account is disabled.
        """
        if isinstance(user, EnabledAwareInterface) and not user.is_enabled():
            raise DisabledError(user)

    @override
    async def check_post_auth(
        self,
        user: UserInterface,
        token: TokenInterface | None = None,
    ) -> None:
        """Do nothing after authentication: this checker gates only the account state."""
        del user, token
