"""The badge naming the user an authentication is for."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_security_core.exception import AuthenticationServiceError
from xtr_security_core.user.user_interface import UserInterface

from .badge_interface import BadgeInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

__all__ = ["MAX_USERNAME_LENGTH", "UserBadge"]

MAX_USERNAME_LENGTH: Final = 4096
"""The longest identifier a badge accepts, guarding against a runaway input."""


@final
class UserBadge(BadgeInterface):
    """Names the user an authentication is for, and loads them on demand.

    The identifier is what authentication proved — a username, a token's
    ``sub``. A loader turns it into a user: passed in by the authenticator, or
    set by a user-provider listener during the passport check. Attributes
    carried alongside — a token's claims — are handed to the loader, so an
    attributes-based provider can build the user from more than the identifier.

    The badge resolves as soon as its loader is set; :meth:`get_user` runs the
    loader once and caches the user. An identifier longer than
    :data:`MAX_USERNAME_LENGTH` is refused at construction.
    """

    __slots__ = ("_attributes", "_identifier", "_user", "_user_loader")

    def __init__(
        self,
        identifier: str,
        user_loader: Callable[..., UserInterface | Awaitable[UserInterface]] | None = None,
        attributes: Mapping[str, object] | None = None,
        identifier_normalizer: Callable[[str], str] | None = None,
    ) -> None:
        """Record the identifier, an optional loader and the attributes.

        Args:
            identifier: What authentication proved the caller to be.
            user_loader: Turns the identifier (and attributes) into a user;
                a provider listener sets one during the check when omitted.
            attributes: Extra data — a token's claims — handed to the loader.
            identifier_normalizer: Applied to the identifier before it is
                stored, for a provider that folds case or trims it.

        Raises:
            BadCredentialsError: When the identifier is empty.
            InvalidArgumentError: When the identifier is longer than
                :data:`MAX_USERNAME_LENGTH`.
        """
        from xtr_security_core.exception import (  # noqa: PLC0415 -- local: only the constructor validates
            BadCredentialsError,
            InvalidArgumentError,
        )

        if identifier_normalizer is not None:
            identifier = identifier_normalizer(identifier)
        if not identifier:
            raise BadCredentialsError("The user identifier must not be empty.")
        if len(identifier) > MAX_USERNAME_LENGTH:
            raise InvalidArgumentError(
                f"The user identifier is too long, {MAX_USERNAME_LENGTH} characters at most.",
            )
        self._identifier = identifier
        self._user_loader = user_loader
        self._attributes: dict[str, object] = dict(attributes) if attributes is not None else {}
        self._user: UserInterface | None = None

    def get_user_identifier(self) -> str:
        """Return the identifier this badge names."""
        return self._identifier

    def get_loaded_user(self) -> UserInterface:
        """Return the user :meth:`get_user` already loaded, without doing I/O.

        Raises:
            AuthenticationServiceError: When the user has not been loaded yet,
                which a token being created before the passport check would be.
        """
        if self._user is None:
            raise AuthenticationServiceError(
                "The user badge's user has not been loaded; the passport check must run first.",
            )
        return self._user

    def get_attributes(self) -> Mapping[str, object]:
        """Return the attributes handed to the loader."""
        return dict(self._attributes)

    def get_user_loader(self) -> Callable[..., UserInterface | Awaitable[UserInterface]] | None:
        """Return the loader set for this badge, or ``None``."""
        return self._user_loader

    def set_user_loader(
        self,
        user_loader: Callable[..., UserInterface | Awaitable[UserInterface]],
    ) -> None:
        """Set the loader a provider listener resolved for this badge."""
        self._user_loader = user_loader

    async def get_user(self) -> UserInterface:
        """Load the user this badge names, once, and return it.

        The loader is called with the identifier, and with the attributes when
        it accepts a second argument. Its result is awaited when it is an
        awaitable.

        Raises:
            AuthenticationServiceError: When no loader was set, or the loader
                returned something that is not a user.
            UserNotFoundError: When the loader reports no such user.
        """
        if self._user is not None:
            return self._user
        if self._user_loader is None:
            raise AuthenticationServiceError(
                "No user loader is set on the user badge; a user provider must set one.",
            )
        result = self._call_loader(self._user_loader)
        loaded: object = await result if inspect.isawaitable(result) else result
        if not isinstance(loaded, UserInterface):
            raise AuthenticationServiceError("The user loader did not return a user.")
        self._user = loaded
        return loaded

    def _call_loader(
        self,
        loader: Callable[..., UserInterface | Awaitable[UserInterface]],
    ) -> object:
        """Call ``loader`` with the identifier, and the attributes when it takes them."""
        try:
            signature = inspect.signature(loader)
        except (TypeError, ValueError):
            return loader(self._identifier)
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        takes_varargs = any(
            parameter.kind is inspect.Parameter.VAR_POSITIONAL
            for parameter in signature.parameters.values()
        )
        if len(positional) >= 2 or takes_varargs:  # noqa: PLR2004 -- identifier plus attributes
            return loader(self._identifier, dict(self._attributes))
        return loader(self._identifier)

    @override
    def is_resolved(self) -> bool:
        """Tell whether a loader is set, so the user can be loaded."""
        return self._user_loader is not None
