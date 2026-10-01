"""The step that decides a request against a firewall's access-control rules."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_core.authorization.access_decision import AccessDecision
from xtr_security_core.authorization.voter.authenticated_voter import AuthenticatedVoter
from xtr_security_core.exception import AccessDeniedError

if TYPE_CHECKING:
    from starlette.requests import Request
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.access_decision_manager_interface import (
        AccessDecisionManagerInterface,
    )

    from xtr_security_http.access_map_interface import AccessMapInterface

__all__ = ["AccessListener"]


@final
class AccessListener:
    """Requires of a request whatever its firewall's first matching rule demands.

    Run after authentication, inside the firewall. It finds the first access
    rule the request matches and decides the token against that rule's one
    attribute. A ``PUBLIC_ACCESS`` rule short-circuits — the resource is open,
    so no decision is made. A request matching no rule is left alone, its
    access decided by whatever the route itself requires.
    """

    __slots__ = ("_access_decision_manager", "_access_map")

    def __init__(
        self,
        access_map: AccessMapInterface,
        access_decision_manager: AccessDecisionManagerInterface,
    ) -> None:
        """Record the rules to match and the manager that decides them."""
        self._access_map = access_map
        self._access_decision_manager = access_decision_manager

    async def check_access(self, request: Request, token: TokenInterface) -> None:
        """Decide ``token`` against the first rule ``request`` matches.

        Raises:
            AccessDeniedError: When a matching rule's attribute is not granted,
                carrying the decision so a handler can explain or challenge.
        """
        attribute = self._access_map.get_attribute(request)
        if attribute is None or attribute == AuthenticatedVoter.PUBLIC_ACCESS:
            return
        decision = AccessDecision()
        granted = await self._access_decision_manager.decide(
            token,
            [attribute],
            access_decision=decision,
        )
        if not granted:
            raise AccessDeniedError(
                "Access to the requested resource is denied.",
                attributes=(attribute,),
                access_decision=decision,
            )
