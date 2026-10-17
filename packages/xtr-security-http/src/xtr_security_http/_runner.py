"""The one pass a firewall makes over a request: authenticate, decide, scope.

Shared by the bound and the unbound firewall dependency. Authentication runs
once per firewall per request — memoised on the request's security state —
while the access and scope decisions run on every call, since two schemes in
one request carry different scope sets.

The request is matched and authenticated as a message — the one the kernel
builds for the request being served — and the per-request state it leaves
behind rides the security state carrier the glue creates from the request's
state bag. The firewall map, the token storage and the access-decision
manager are handed in by the caller — the firewall scheme fills them from
the request scope with ``Injected[...]`` markers — so nothing here reaches
into the container.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authorization.access_decision import AccessDecision
from xtr_security_core.exception import AccessDeniedError

from ._security_state import CarriedResponse, SecurityState
from .authorization.oauth2_scope_voter import oauth2_scope

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.access_decision_manager_interface import (
        AccessDecisionManagerInterface,
    )

    from xtr_security_http.firewall_context_interface import FirewallContextInterface
    from xtr_security_http.firewall_map_interface import FirewallMapInterface

__all__ = ["run_firewall"]


async def run_firewall(  # noqa: PLR0913 -- the message, its scopes, the state and three injected services
    name: str | None,
    message: ServerRequestInterface,
    scopes: Sequence[str],
    *,
    state: SecurityState,
    firewall_map: FirewallMapInterface,
    token_storage: TokenStorageInterface,
    access_decision_manager: AccessDecisionManagerInterface,
) -> None:
    """Run the firewall ``name`` (or the one matching ``message``) over the request.

    Raises:
        UnknownFirewallError: When ``name`` names no configured firewall.
        AuthenticationError: When authentication fails and no handler answered.
        AccessDeniedError: When an access rule or a scope is not granted.
        CarriedResponse: When a success or failure handler produced a response.
    """
    context = await _resolve(firewall_map, name, message)
    if context is None or not context.security:
        if scopes:
            raise AccessDeniedError(
                "A scoped resource was reached with no firewall to authenticate the caller.",
            )
        return

    state.firewall_context = context
    await _authenticate_once(context, message, state)
    token = token_storage.get_token() or NullToken()
    state.token = token
    await context.access_listener.check_access(message, token)
    if scopes:
        await _check_scopes(access_decision_manager, token, scopes)


async def _resolve(
    firewall_map: FirewallMapInterface, name: str | None, message: ServerRequestInterface
) -> FirewallContextInterface | None:
    """Return the firewall to run: the one named, or the first that matches."""
    if name is not None:
        return firewall_map.get(name)
    return await firewall_map.match(message)


async def _authenticate_once(
    context: FirewallContextInterface,
    message: ServerRequestInterface,
    state: SecurityState,
) -> None:
    """Authenticate the request under ``context`` at most once, memoised by name.

    The manager's supports pass runs first, parking what it learned on the
    request's state; the pass that authenticates consumes it. A supports pass
    that no authenticator answered is a pass that authenticated — the
    request goes on anonymous, memoised like one that did.

    Only a settled outcome is memoised: ``None`` for a pass that authenticated,
    the exception for one that did not. Recording a crash as a pass would let a
    later call over the same request skip authentication and go on with a null
    token, so whatever the authenticators raised — a failure the handlers own or
    a bug they do not — is recorded and raised again by every later call. A later
    call raises a fresh instance of the recorded error's type and message rather
    than the stored instance itself, so re-raising it does not splice this
    request's traceback onto the one the first call already unwound, nor let a
    caller that mutates the caught exception change what a later call raises.

    Raises:
        AuthenticationError: When authentication fails, on this call and every
            later one this request.
        BaseException: Whatever else authentication raised, re-raised by every
            later call this request rather than passing it off as authenticated.
        CarriedResponse: When a handler produced a response to send.
    """
    memo = state.authenticated_firewalls
    if context.name in memo:
        recorded = memo[context.name]
        if recorded is not None:
            raise type(recorded)(str(recorded))
        return
    try:
        if context.authenticator_manager.supports(message, state) is False:
            memo[context.name] = None
            return
        response = await context.authenticator_manager.authenticate_request(message, state)
    except BaseException as error:
        memo[context.name] = error
        raise
    else:
        memo[context.name] = None
    if response is not None:
        raise CarriedResponse(response)


async def _check_scopes(
    access_decision_manager: AccessDecisionManagerInterface,
    token: TokenInterface,
    scopes: Sequence[str],
) -> None:
    """Decide the accumulated scopes against the token, denying when short.

    Raises:
        AccessDeniedError: When the token lacks a required scope, carrying the
            scope attribute so the exception listener answers with a scope
            challenge.
    """
    attribute = oauth2_scope(*scopes)
    decision = AccessDecision()
    granted = await access_decision_manager.decide(token, [attribute], access_decision=decision)
    if not granted:
        raise AccessDeniedError(
            "The token does not carry the scope this resource requires.",
            attributes=(attribute,),
            access_decision=decision,
        )
