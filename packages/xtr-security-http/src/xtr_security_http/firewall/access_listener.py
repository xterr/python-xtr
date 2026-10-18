"""The chain's access step: the rules a request matched, decided over the request."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authorization.access_decision import AccessDecision
from xtr_security_core.authorization.voter.authenticated_voter import AuthenticatedVoter
from xtr_security_core.exception import AccessDeniedError, InvalidArgumentError

from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .abstract_listener import AbstractListener

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.access_decision_manager_interface import (
        AccessDecisionManagerInterface,
    )

    from xtr_security_http.access_map_interface import AccessMapInterface

__all__ = ["AccessListener"]


@final
class AccessListener(AbstractListener):
    """Requires of a request whatever its firewall's first matching rule demands.

    A chain step: ``supports`` asks the access map which rule the request
    matches and parks the attributes that rule requires on the request's
    security state, answering ``True`` when there is something to decide and
    ``None`` — the lazy join — when there is not, so a public-only or
    unmatched request still reaches the step. ``authenticate`` reads what
    was parked back, decides the token against it with the request itself as
    the subject, and raises when the decision refuses.

    The token comes from the token storage, a null token standing in for an
    anonymous request: the decision, not the listener, is what turns an
    anonymous request away from a rule that needs authentication. A
    ``PUBLIC_ACCESS`` rule is decided like any other — the authenticated
    voter grants it for every token, null ones included — so the decision
    record explains why the request passed. (Upstream skips a public-only
    match on the lazy response event; this kernel has no such event yet, so
    the branch has nothing to skip on.)

    Until the firewall's chain runs the request, the same rules are decided
    the way the firewall runner always has, through :meth:`check_access`: the
    runner hands the token it authenticated, the listener matches the map
    again and decides. The two paths share the deciding and the refusal; only
    where the token comes from, and where the matched attributes are parked,
    differ.
    """

    __slots__ = ("_access_decision_manager", "_access_map", "_token_storage")

    def __init__(
        self,
        token_storage: TokenStorageInterface,
        access_decision_manager: AccessDecisionManagerInterface,
        access_map: AccessMapInterface,
        exception_on_no_token: bool = False,
    ) -> None:
        """Record the storage, the manager and the rules this step decides with.

        Args:
            token_storage: Where the step reads the token the request was
                authenticated under.
            access_decision_manager: Decides the token against the matched
                rule's attributes.
            access_map: The firewall's rules, matched to find what a request
                must satisfy.
            exception_on_no_token: A vestigial flag from an older contract,
                kept to fail loudly in a caller that still passes it: only
                ``False`` is accepted.

        Raises:
            InvalidArgumentError: When ``exception_on_no_token`` is true —
                the step decides an anonymous request against a null token by
                design, so a caller asking it to refuse one instead is asking
                for a behaviour this step no longer has.
        """
        if exception_on_no_token:
            raise InvalidArgumentError(
                "The access listener's exception_on_no_token argument must be False: "
                "the listener decides an anonymous request against a null token.",
            )
        self._token_storage = token_storage
        self._access_decision_manager = access_decision_manager
        self._access_map = access_map

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        """Park what the matched rule requires, and answer whether there is a decision to make.

        The attributes are parked on the request's security state — the
        carrier the chain's caller reaches through the state bag parked on
        the request — for ``authenticate`` to read back, so the matching runs
        once for both hooks. A rule that requires nothing of the request, or
        only public access, still joins the chain lazily: ``None``, not
        ``False``, because the step wants its say even when the request's
        head committed it to nothing.
        """
        attributes, _channel = await self._access_map.get_patterns(request)
        security_state_of(state_bag_of(request)).attributes[
            SecurityRequestAttributes.ACCESS_CONTROL_ATTRIBUTES
        ] = attributes
        if attributes and attributes != (AuthenticatedVoter.PUBLIC_ACCESS,):
            return True
        return None

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        """Decide the request against the attributes the supports pass parked.

        The parked attributes are read and removed, so a later ask over the
        same request finds nothing parked and decides nothing. Nothing parked
        at all means no supports pass ran — the request is left alone, its
        access decided by whatever the route itself requires.

        Raises:
            AccessDeniedError: When the decision refuses, carrying the
                attributes, the request as the subject, and the decision.
        """
        state = security_state_of(request_event.state)
        parked = state.attributes.pop(SecurityRequestAttributes.ACCESS_CONTROL_ATTRIBUTES, None)
        if not parked:
            return
        # Only this listener's supports pass parks under the key, as a tuple
        # of attribute strings; the cast reads that handoff back.
        attributes = cast("tuple[str, ...]", parked)
        token = self._token_storage.get_token() or NullToken()
        await self._decide(request_event.request, token, attributes)

    async def check_access(self, request: ServerRequestInterface, token: TokenInterface) -> None:
        """Decide ``token`` against the first rule ``request`` matches.

        The path the firewall runner drives: it has authenticated the request
        and hands the token it authenticated, so the step matches the map and
        decides, parking nothing. A rule that requires only public access
        short-circuits here — the resource is open, so no decision is made —
        and a request matching no rule is left alone.

        Raises:
            AccessDeniedError: When a matching rule's attributes are not
                granted, carrying the attributes, the request as the subject,
                and the decision.
        """
        attributes, _channel = await self._access_map.get_patterns(request)
        if not attributes or attributes == (AuthenticatedVoter.PUBLIC_ACCESS,):
            return
        await self._decide(request, token, attributes)

    @staticmethod
    @override
    def get_priority() -> int:
        """Return the chain position: after authentication, before the cleanup steps."""
        return -255

    async def _decide(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
        attributes: tuple[str, ...],
    ) -> None:
        """Decide ``token`` over ``request`` — the subject — against ``attributes``.

        Raises:
            AccessDeniedError: When the decision refuses. The local error
                composes the decision's message onto the listener's reason,
                so the refusal explains itself the way every access denial
                this family raises does.
        """
        decision = AccessDecision()
        granted = await self._access_decision_manager.decide(
            token,
            attributes,
            subject=request,
            access_decision=decision,
        )
        if not granted:
            raise AccessDeniedError(
                "Access to the requested resource is denied.",
                attributes=attributes,
                subject=request,
                access_decision=decision,
            )
