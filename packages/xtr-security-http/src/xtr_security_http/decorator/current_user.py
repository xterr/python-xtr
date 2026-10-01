"""The marker that injects the authenticated user into an endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from fastapi.params import Depends as DependsParam

# The framework reads the dependency's signature at runtime to fill it from the
# container, so the injection marker and the storage type stay importable here.
from xtr_dependency_injection import Injected  # noqa: TC002
from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002
    TokenStorageInterface,
)
from xtr_security_core.exception import AuthenticationCredentialsNotFoundError, UnsupportedUserError

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["CurrentUser"]


@final
class CurrentUser(DependsParam):
    """Injects the current user into an endpoint parameter.

    Used as ``Annotated[User, CurrentUser()]``. By default the parameter must
    have a user: an anonymous request raises
    :class:`~xtr_security_core.exception.AuthenticationCredentialsNotFoundError`,
    which becomes a ``401``. Passing ``optional=True`` — for a parameter typed
    ``User | None`` — returns ``None`` for an anonymous request instead. When
    ``user_class`` is given, a user of another class raises
    :class:`~xtr_security_core.exception.UnsupportedUserError`. The dependency never
    appears in the generated schema.

    The token storage the current user comes from is a container-provided
    dependency of the resolver, declared with :data:`~xtr_dependency_injection.Injected`
    — so the request's scoped storage is filled by the framework, never fetched
    from the container by hand.

    (FastAPI does not hand a dependency the annotation of the parameter it
    fills, so nullability and the expected class are stated on the marker
    rather than read from ``User | None`` — the one departure from the
    spelling in the plan; see the package's DoneClaim.)

    Attributes:
        optional: Whether an anonymous request yields ``None`` instead of raising.
        user_class: The class a user must be, or ``None`` to accept any.
    """

    optional: bool  # pyright: ignore[reportUninitializedInstanceVariable]
    user_class: type | None  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(self, user_class: type | None = None, *, optional: bool = False) -> None:
        """Inject the current user, optionally typed and optionally nullable."""
        object.__setattr__(self, "optional", optional)
        object.__setattr__(self, "user_class", user_class)
        super().__init__(dependency=self._resolve, use_cache=True)

    async def _resolve(
        self,
        token_storage: Injected[TokenStorageInterface],
    ) -> UserInterface | None:
        """Return the current user, or ``None`` / an error for an anonymous request.

        Raises:
            AuthenticationCredentialsNotFoundError: When no user is
                authenticated and the marker is not ``optional``.
            UnsupportedUserError: When the user is not of ``user_class``.
        """
        token = token_storage.get_token()
        user = token.get_user() if token is not None else None
        if user is None:
            if self.optional:
                return None
            raise AuthenticationCredentialsNotFoundError(
                "No authenticated user is available for this request.",
            )
        if self.user_class is not None and not isinstance(user, self.user_class):
            raise UnsupportedUserError(
                f"The current user is not a {self.user_class.__name__}.",
            )
        return user
