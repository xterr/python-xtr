"""The service that reads the current user out of the request's token storage."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
    TokenStorageInterface,
)
from xtr_security_core.exception import (
    AuthenticationCredentialsNotFoundError,
    UnsupportedUserError,
)

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http.decorator.current_user import CurrentUser

__all__ = ["UserValueResolver"]


@final
class UserValueResolver:
    """Fills a route argument with the user the request authenticated.

    The route marker —
    :class:`~xtr_security_http.decorator.current_user.CurrentUser` — states
    what the argument wants: the class (or classes) the user must be, and
    whether an anonymous request may yield ``None``. This service reads that
    statement against the request's token storage, so the type matching and
    the two denials live in one place — testable without the web framework,
    and reusable behind any other filling mechanism.

    The denials stay distinct, so a caller can tell them apart: an anonymous
    request against a marker that does not allow it raises
    :class:`~xtr_security_core.exception.AuthenticationCredentialsNotFoundError`
    (answered ``401``), while a user of another class raises
    :class:`~xtr_security_core.exception.UnsupportedUserError`.
    """

    __slots__ = ("_token_storage",)

    def __init__(self, token_storage: TokenStorageInterface) -> None:
        """Build the resolver over the request's token storage.

        Args:
            token_storage: Holds the token the firewall authenticated for
                this request.
        """
        self._token_storage = token_storage

    async def resolve(self, current_user: CurrentUser) -> UserInterface | None:
        """Return the user ``current_user`` asks for, or ``None`` when it may.

        Raises:
            AuthenticationCredentialsNotFoundError: When no user is
                authenticated and ``current_user`` is not ``optional``.
            UnsupportedUserError: When the user is not of the class (or any
                of the classes) ``current_user`` states.
        """
        token = self._token_storage.get_token()
        user = token.get_user() if token is not None else None
        if user is None:
            if current_user.optional:
                return None
            raise AuthenticationCredentialsNotFoundError(
                "There is no logged-in user to pass to the argument; "
                "make the marker optional to allow anonymous access to the action.",
            )
        user_class = current_user.user_class
        if user_class is not None and not isinstance(user, user_class):
            expected = (
                user_class.__name__
                if isinstance(user_class, type)
                else "|".join(cls.__name__ for cls in user_class)
            )
            raise UnsupportedUserError(
                f'The logged-in user is an instance of "{type(user).__name__}" '
                f'but a user of type "{expected}" is expected.',
            )
        return user
