"""The marker that injects the authenticated user into an endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from fastapi.params import Depends as DependsParam

# The framework reads the dependency's signature at runtime to fill it from the
# container, so the injection marker and the resolver type stay importable here.
from xtr_dependency_injection import Injected  # noqa: TC002

from xtr_security_http.resolver.user_value_resolver import UserValueResolver  # noqa: TC001

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["CurrentUser"]


@final
class CurrentUser(DependsParam):
    """Injects the current user into an endpoint parameter.

    Used as ``Annotated[User, CurrentUser()]``. The marker is pure metadata —
    what the argument wants — and the reading of the request's security state
    happens in the injectable
    :class:`~xtr_security_http.resolver.user_value_resolver.UserValueResolver`
    the thin dependency delegates to.

    By default the parameter must have a user: an anonymous request raises
    :class:`~xtr_security_core.exception.AuthenticationCredentialsNotFoundError`,
    which becomes a ``401``. Passing ``optional=True`` — for a parameter typed
    ``User | None`` — returns ``None`` for an anonymous request instead. When
    ``user_class`` is given (one class, or several as a tuple for a union), a
    user of another class raises
    :class:`~xtr_security_core.exception.UnsupportedUserError`. Passing
    ``disabled=True`` switches the resolution off for this one parameter —
    the dependency yields ``None`` without reading the request — for an
    application that enables the resolver globally but excludes a route.

    (The web framework does not hand a dependency the annotation of the
    parameter it fills, so nullability and the expected class are stated on
    the marker rather than read from ``User | None``.)

    The dependency never appears in the generated schema.

    Attributes:
        optional: Whether an anonymous request yields ``None`` instead of raising.
        user_class: The class (or tuple of classes) a user must be, or ``None``
            to accept any.
        disabled: Whether this marker's resolution is switched off.
    """

    optional: bool  # pyright: ignore[reportUninitializedInstanceVariable]
    user_class: type | tuple[type, ...] | None  # pyright: ignore[reportUninitializedInstanceVariable]
    disabled: bool  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(
        self,
        user_class: type | tuple[type, ...] | None = None,
        *,
        optional: bool = False,
        disabled: bool = False,
    ) -> None:
        """Inject the current user, optionally typed, nullable, and disablable."""
        object.__setattr__(self, "optional", optional)
        object.__setattr__(self, "user_class", user_class)
        object.__setattr__(self, "disabled", disabled)
        super().__init__(dependency=self._resolve, use_cache=True)

    async def _resolve(self, resolver: Injected[UserValueResolver]) -> UserInterface | None:
        """Return the current user, or ``None`` when disabled or allowed anonymous.

        Raises:
            AuthenticationCredentialsNotFoundError: When no user is
                authenticated and the marker is not ``optional``.
            UnsupportedUserError: When the user is not of ``user_class``.
        """
        if self.disabled:
            return None
        return await resolver.resolve(self)
