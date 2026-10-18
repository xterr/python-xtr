"""The marker that injects the authenticated token into an endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from fastapi.params import Depends as DependsParam

# The framework reads the dependency's signature at runtime to fill it from the
# container, so the injection marker and the resolver type stay importable here.
from xtr_dependency_injection import Injected  # noqa: TC002

from xtr_security_http.resolver.security_token_resolver import SecurityTokenResolver  # noqa: TC001

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["CurrentToken"]


@final
class CurrentToken(DependsParam):
    """Injects the token the request authenticated into an endpoint parameter.

    Used as ``Annotated[TokenInterface, CurrentToken()]`` — for an endpoint
    that decides something itself off the roles or the attributes
    authentication settled on. The marker is pure metadata; the reading of the
    request's security state happens in the injectable
    :class:`~xtr_security_http.resolver.security_token_resolver.SecurityTokenResolver`
    the thin dependency delegates to.

    By default the parameter must have a token: an anonymous request raises
    :class:`~xtr_security_core.exception.AuthenticationCredentialsNotFoundError`,
    which becomes a ``401``. Passing ``optional=True`` — for a parameter typed
    ``TokenInterface | None`` — returns ``None`` for an anonymous request
    instead. The dependency never appears in the generated schema.

    Attributes:
        optional: Whether an anonymous request yields ``None`` instead of raising.
    """

    optional: bool  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(self, *, optional: bool = False) -> None:
        """Inject the current token, optionally nullable."""
        object.__setattr__(self, "optional", optional)
        super().__init__(dependency=self._resolve, use_cache=True)

    async def _resolve(self, resolver: Injected[SecurityTokenResolver]) -> TokenInterface | None:
        """Return the current token, or ``None`` for an anonymous request when allowed.

        Raises:
            AuthenticationCredentialsNotFoundError: When no token is
                authenticated and the marker is not ``optional``.
        """
        return await resolver.resolve(self)
