"""The FastAPI security object a firewall is."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from fastapi.security import HTTPBearer, SecurityScopes
from fastapi.security.base import SecurityBase

# The framework reads the dependency's __call__ signature at runtime to inject
# these, so they — and the service types the container fills — cannot live
# behind TYPE_CHECKING.
from starlette.requests import Request  # noqa: TC002
from xtr_dependency_injection import Injected  # noqa: TC002
from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002
    TokenStorageInterface,
)
from xtr_security_core.authorization.access_decision_manager_interface import (  # noqa: TC002
    AccessDecisionManagerInterface,
)

from ._runner import run_firewall
from .exception.firewall_not_booted_error import FirewallNotBootedError
from .firewall_map_interface import FirewallMapInterface  # noqa: TC001 -- filled into __call__
from .firewall_scheme_registry import active_firewall_scheme_registry

if TYPE_CHECKING:
    from fastapi.openapi.models import SecurityBase as SecurityBaseModel

__all__ = ["FirewallScheme"]

_GENERIC_SCHEME_NAME = "firewall"


@final
class FirewallScheme(SecurityBase):
    """A firewall, seen by FastAPI as both a dependency and a security scheme.

    As a dependency, calling it runs the firewall for the request — authenticate
    once, then decide access and any accumulated scopes. As a
    :class:`~fastapi.security.base.SecurityBase`, its ``model`` and
    ``scheme_name`` — read only when the schema is generated — describe the
    firewall in OpenAPI: a bound firewall's from the registry the kernel filled
    at boot, an unbound one's a generic bearer scheme.
    """

    def __init__(self, name: str | None) -> None:
        """Build the scheme for the firewall ``name``, or an unbound one for ``None``."""
        self._name = name
        self._generic = HTTPBearer(auto_error=False, bearerFormat="JWT", scheme_name="firewall")

    async def __call__(
        self,
        request: Request,
        security_scopes: SecurityScopes,
        firewall_map: Injected[FirewallMapInterface],
        token_storage: Injected[TokenStorageInterface],
        access_decision_manager: Injected[AccessDecisionManagerInterface],
    ) -> None:
        """Run the firewall for ``request``, enforcing the accumulated scopes."""
        await run_firewall(
            self._name,
            request,
            tuple(security_scopes.scopes),
            firewall_map=firewall_map,
            token_storage=token_storage,
            access_decision_manager=access_decision_manager,
        )

    # These read the OpenAPI model dynamically at schema-generation time, so they
    # are properties over the plain attributes the base declares — the override is
    # deliberate and the type checker cannot see it is compatible.
    @property
    def model(  # pyright: ignore[reportIncompatibleVariableOverride, reportImplicitOverride]
        self,
    ) -> SecurityBaseModel:
        """Return the firewall's OpenAPI model, resolved when the schema is built.

        Raises:
            FirewallNotBootedError: When a bound firewall's scheme is read
                before the kernel filled the registry, or outside a request.
        """
        if self._name is None:
            return self._generic.model
        registry = active_firewall_scheme_registry()
        entry = registry.get(self._name) if registry is not None else None
        if entry is None:
            raise FirewallNotBootedError(self._not_booted_message())
        return entry.model

    @property
    def scheme_name(  # pyright: ignore[reportIncompatibleVariableOverride, reportImplicitOverride]
        self,
    ) -> str:
        """Return the firewall's OpenAPI scheme name, an unbound one's generic.

        Raises:
            FirewallNotBootedError: When a bound firewall's scheme is read
                before the kernel filled the registry, or outside a request.
        """
        if self._name is None:
            return _GENERIC_SCHEME_NAME
        registry = active_firewall_scheme_registry()
        entry = registry.get(self._name) if registry is not None else None
        if entry is None:
            raise FirewallNotBootedError(self._not_booted_message())
        return entry.scheme_name

    def _not_booted_message(self) -> str:
        """Name the firewall whose scheme was read before the kernel registered it."""
        return (
            f'The OpenAPI scheme of the firewall "{self._name}" was read before the '
            f"kernel registered it, or outside a request."
        )
