"""The event that decides whether a refreshed user logs its token out."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["CheckRefreshedUserEvent"]


@final
class CheckRefreshedUserEvent(Event):
    """Announces that a session token's user was just reloaded from its provider.

    Dispatched while the context listener refreshes the token it read from
    the session, once a provider has reloaded the user, so a listener can
    weigh in on whether the reload changed the user enough to
    deauthenticate: an account an administrator disabled during the session,
    a permission withdrawn since the login. The verdict the listener itself
    computed — password, roles, identifier — is seeded in, so a listener
    starts from the built-in answer and may confirm, add its own reason, or
    clear one it does not want to act on.

    Listeners run on every request of a stateful firewall: keep them cheap
    and free of side effects.

    Not a frozen dataclass: a listener changes the verdict.

    Attributes:
        token: The token the session stored, whose user was reloaded.
        original_user: The user as the session stored it.
        refreshed_user: The user the provider just reloaded.
    """

    def __init__(
        self,
        token: TokenInterface,
        original_user: UserInterface,
        refreshed_user: UserInterface,
        user_changed: bool = False,
    ) -> None:
        """Record the reload, seeded with the built-in comparison's verdict.

        Args:
            token: The token the session stored, whose user was reloaded.
            original_user: The user as the session stored it.
            refreshed_user: The user the provider just reloaded.
            user_changed: The verdict the listener itself computed — the
                built-in comparison of password, roles and identifier.
        """
        self._token = token
        self._original_user = original_user
        self._refreshed_user = refreshed_user
        self._user_changed = user_changed
        self._exception: AuthenticationError | None = None

    def get_token(self) -> TokenInterface:
        """Return the token the session stored, whose user was reloaded."""
        return self._token

    def get_original_user(self) -> UserInterface:
        """Return the user as it was stored in the session."""
        return self._original_user

    def get_refreshed_user(self) -> UserInterface:
        """Return the user as the provider just reloaded it."""
        return self._refreshed_user

    def is_user_changed(self) -> bool:
        """Return the verdict as it stands: whether the token is deauthenticated."""
        return self._user_changed

    def set_user_changed(self, changed: bool, exception: AuthenticationError | None = None) -> None:
        """Deauthenticate the token, or keep it despite what decided otherwise.

        A listener adding its own reason hands the error carrying it, for
        the deauthentication event to pass on; one clearing the verdict
        clears the reason with it, because a reason with no verdict left is
        a reason nothing will read.

        Args:
            changed: The new verdict.
            exception: The reason to deauthenticate, when ``changed`` is
                true; kept from a previous listener when left out.
        """
        self._user_changed = changed
        # A verdict kept or added without a reason of its own keeps the
        # reason an earlier listener gave; a cleared verdict clears the
        # reason with it.
        self._exception = (
            (exception if exception is not None else self._exception) if changed else None
        )

    def get_exception(self) -> AuthenticationError | None:
        """Return the reason a listener gave to deauthenticate, if one did."""
        return self._exception
