"""The provider loop that reloads a session token's user."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_logging_contracts import NullLogger
from xtr_security_core.exception import UnsupportedUserError, UserNotFoundError

from xtr_security_http.event.check_refreshed_user_event import CheckRefreshedUserEvent

from .refresh_user_result import RefreshUserResult
from .user_changed import has_user_changed

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

__all__ = ["UserRefresher"]


@final
class UserRefresher:
    """Reloads a session token's user through the firewall's providers.

    The providers are tried in order, each asked first whether it loads the
    class of user the token carries; one that does reloads the user, and the
    reload is weighed — the listener's own comparison, then every listener of
    the refreshed-user check, each of which may set the verdict or clear it.
    The first provider whose reload held wins: its user is set on the token,
    and the token is the result.

    A provider that does not support the class is skipped; one that refuses
    the user hands it to the next; one that cannot find the user contributes
    its class to the deauthentication, because a session whose user no
    provider can find is a session about nobody.
    """

    __slots__ = ("_dispatcher", "_logger", "_user_providers")

    def __init__(
        self,
        user_providers: Sequence[UserProviderInterface],
        logger: LoggerInterface | None = None,
        dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Record the providers the reload runs through, in order.

        Args:
            user_providers: The providers a session token's user is reloaded
                through, in order; the first that supports the user's class
                and vouches for it wins.
            logger: Writes the reload's decisions, when given.
            dispatcher: Where the refreshed-user check is announced, when
                given.
        """
        self._user_providers = tuple(user_providers)
        self._logger = logger or NullLogger()
        self._dispatcher = dispatcher

    async def refresh(self, token: TokenInterface, user: UserInterface) -> RefreshUserResult:
        """Reload ``token``'s ``user``, deauthenticating on a change.

        Raises:
            UnsupportedUserError: When no provider supports the class of
                ``user``.
        """
        user_class = type(user)
        user_changed_by: list[type] = []
        user_not_found_by: list[type] = []
        user_changed_because: AuthenticationError | None = None

        for provider in self._user_providers:
            if not provider.supports_class(user_class):
                continue
            try:
                refreshed_user = await provider.refresh_user(user)
            except UnsupportedUserError:
                continue
            except UserNotFoundError:
                self._logger.info(
                    "The user could not be found by the user provider that supports it.",
                    {
                        "username": user.get_user_identifier(),
                        "provider": type(provider).__name__,
                    },
                )
                user_not_found_by.append(type(provider))
                continue

            user_changed, listener_exception = await self._weigh(token, user, refreshed_user)
            if user_changed:
                user_changed_by.append(type(provider))
                if user_changed_because is None:
                    user_changed_because = listener_exception
                self._logger.debug(
                    "Cannot refresh the token because the user has changed.",
                    {"username": refreshed_user.get_user_identifier()},
                )
                continue

            token.set_user(refreshed_user)
            self._logger.debug(
                "The user was reloaded from a user provider.",
                {
                    "provider": type(provider).__name__,
                    "username": refreshed_user.get_user_identifier(),
                },
            )
            return RefreshUserResult(token)

        if user_changed_by:
            reason = (
                str(user_changed_because)
                if user_changed_because is not None
                else "the user has changed"
            )
            return RefreshUserResult(None, reason, tuple(user_changed_by), user_changed_because)
        if user_not_found_by:
            return RefreshUserResult(
                None,
                "the user could not be found by any user provider",
                tuple(user_not_found_by),
            )
        raise UnsupportedUserError(
            f"There is no user provider for a user of the class {user_class.__name__}: no "
            "provider's supports_class() answers for it, so the session token's user cannot "
            "be reloaded.",
        )

    async def _weigh(
        self,
        token: TokenInterface,
        user: UserInterface,
        refreshed_user: UserInterface,
    ) -> tuple[bool, AuthenticationError | None]:
        """Weigh a provider's reload of ``user``, and answer the verdict with its reason.

        The listener's own comparison seeds the verdict, and every listener
        of the refreshed-user check may set it or clear it, handing the
        error that is its reason along. The reason answered beside the
        verdict is the first one a listener gave, kept for the
        deauthentication event to carry.
        """
        user_changed = has_user_changed(token, user, refreshed_user)
        if self._dispatcher is None:
            return user_changed, None
        event = CheckRefreshedUserEvent(token, user, refreshed_user, user_changed)
        _ = await self._dispatcher.dispatch(event)
        return event.is_user_changed(), event.get_exception()
