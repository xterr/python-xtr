"""The provider loop that reloads a session token's user."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_logging_contracts import NullLogger
from xtr_security_core.authentication.token.switch_user_token import SwitchUserToken
from xtr_security_core.exception import UnsupportedUserError, UserNotFoundError

from xtr_security_http.event.check_refreshed_user_event import CheckRefreshedUserEvent
from xtr_security_http.session.session_user import SessionUser

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

    A user the session could keep only as a snapshot arrives as a
    :class:`~xtr_security_http.session.session_user.SessionUser` stand-in,
    and a stand-in is never handed to ``refresh_user`` — a provider may merge
    what it is handed into what it stores, and a stand-in is no user of its
    class. Each provider is asked to load the user by the stand-in's
    identifier instead, one whose answer is of a class it does not support
    is skipped, and the answer is weighed against the stand-in exactly as a
    reload is weighed against the user it reloads.

    A switch token refreshes from the inside out: the original token —
    the impersonator's — is refreshed first, and a reload that
    deauthenticates it deauthenticates the switch with it, because a
    switch whose origin is gone has nothing to return to.
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

    async def refresh(  # noqa: C901 -- the provider loop: one branch per way a provider answers, kept in one place
        self,
        token: TokenInterface,
        user: UserInterface,
    ) -> RefreshUserResult:
        """Reload ``token``'s ``user``, deauthenticating on a change.

        A switch token first has its original token reloaded the same
        way; a reload that deauthenticates the impersonator answers for
        the switch too, with the impersonator's own result.

        Raises:
            UnsupportedUserError: When no provider supports the class of
                ``user`` — for a stand-in, when no provider loads it as a
                class it supports.
        """
        deauthenticated = await self._switch_original_result(token)
        if deauthenticated is not None:
            return deauthenticated
        user_changed_by: list[type] = []
        user_not_found_by: list[type] = []
        user_changed_because: AuthenticationError | None = None

        for provider in self._user_providers:
            try:
                refreshed_user = await self._reloaded_by(provider, user)
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
            if refreshed_user is None:
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
            context: dict[str, object] = {
                "provider": type(provider).__name__,
                "username": refreshed_user.get_user_identifier(),
            }
            if isinstance(token, SwitchUserToken):
                context["impersonator_username"] = token.get_original_token().get_user_identifier()
            self._logger.debug("The user was reloaded from a user provider.", context)
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
        if isinstance(user, SessionUser):
            raise UnsupportedUserError(
                "There is no user provider for the user the session token carries: no "
                "provider loads it by its identifier as a class its supports_class() answers "
                "for, so the session token's user cannot be reloaded.",
            )
        raise UnsupportedUserError(
            f"There is no user provider for a user of the class {type(user).__name__}: no "
            "provider's supports_class() answers for it, so the session token's user cannot "
            "be reloaded.",
        )

    @staticmethod
    async def _reloaded_by(
        provider: UserProviderInterface,
        user: UserInterface,
    ) -> UserInterface | None:
        """Return ``provider``'s reload of ``user``, or ``None`` when it passes on it.

        A user the session rebuilt as its own class is refreshed by a
        provider that supports the class. A stand-in is loaded by its
        identifier instead, and the answer kept only when its class is one
        the provider supports.

        Raises:
            UserNotFoundError: When the provider cannot find the user.
        """
        if isinstance(user, SessionUser):
            try:
                loaded = await provider.load_user_by_identifier(user.get_user_identifier())
            except UnsupportedUserError:
                return None
            return loaded if provider.supports_class(type(loaded)) else None
        if not provider.supports_class(type(user)):
            return None
        try:
            return await provider.refresh_user(user)
        except UnsupportedUserError:
            return None

    async def _switch_original_result(
        self,
        token: TokenInterface,
    ) -> RefreshUserResult | None:
        """Reload a switch token's original first, and answer when it deauthenticates.

        A switch token's user is reloaded only after the impersonator's
        own is — the switch stands on that token — so a reload that
        deauthenticates the impersonator ends the switch with the
        impersonator's result: its reason, its providers, its error. A
        token that is no switch, or whose original carries no user, is
        nothing this reload must settle first.
        """
        if not isinstance(token, SwitchUserToken):
            return None
        original_token = token.get_original_token()
        original_user = original_token.get_user()
        if original_user is None:
            return None
        original_result = await self.refresh(original_token, original_user)
        if original_result.token is None:
            return original_result
        return None

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
