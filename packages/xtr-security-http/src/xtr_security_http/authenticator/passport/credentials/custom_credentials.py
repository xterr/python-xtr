"""A credential verified by a caller-supplied check."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, final

from typing_extensions import override

from .credentials_interface import CredentialsInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = ["CustomCredentials"]


@final
class CustomCredentials(CredentialsInterface):
    """A credential whose verification an authenticator supplies as a check.

    The escape hatch for a scheme the built-in credentials do not cover: the
    check is a callable given the credentials and the resolved user, returning
    whether they are valid — awaited when it returns an awaitable. The
    credentials listener runs it, and a falsy result fails authentication.

    Attributes:
        checker: The callable that verifies ``credentials`` for a user.
        credentials: The value handed to the checker.
    """

    __slots__ = ("_checker", "_credentials", "_resolved")

    def __init__(
        self,
        checker: Callable[..., bool | Awaitable[bool]],
        credentials: object,
    ) -> None:
        """Record the check and the credentials it verifies."""
        self._checker = checker
        self._credentials = credentials
        self._resolved = False

    async def verify(self, user: object) -> bool:
        """Run the check for ``user`` and mark the credentials resolved.

        The checker is called with the credentials and the user; a result that
        is an awaitable is awaited. Resolving happens whatever the outcome — a
        credential is consumed by being checked, valid or not.
        """
        result = self._checker(self._credentials, user)
        if inspect.isawaitable(result):
            result = await result
        self._resolved = True
        return bool(result)

    def get_credentials(self) -> object:
        """Return the credentials the checker verifies."""
        return self._credentials

    @override
    def is_resolved(self) -> bool:
        """Tell whether the check has run."""
        return self._resolved
