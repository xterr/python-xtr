"""The one pass a firewall makes over a request: authenticate, decide, scope.

Shared by the bound and the unbound firewall dependency. Authentication runs
once per firewall per request — memoised on ``request.state`` — while the
access and scope decisions run on every call, since two schemes in one request
carry different scope sets.

The firewall map, the token storage and the access-decision manager are handed
in by the caller — the firewall scheme fills them from the request scope with
``Injected[...]`` markers — so nothing here reaches into the container.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authorization.access_decision import AccessDecision
from xtr_security_core.exception import AccessDeniedError

from ._state import (
    AUTHENTICATED_FIREWALLS_KEY,
    FIREWALL_CONTEXT_KEY,
    TOKEN_KEY,
    CarriedResponse,
)
from .authorization.oauth2_scope_voter import oauth2_scope

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request
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


async def run_firewall(  # noqa: PLR0913 -- the firewall's request, scopes and its three injected services
    name: str | None,
    request: Request,
    scopes: Sequence[str],
    *,
    firewall_map: FirewallMapInterface,
    token_storage: TokenStorageInterface,
    access_decision_manager: AccessDecisionManagerInterface,
) -> None:
    """Run the firewall ``name`` (or the one matching ``request``) over ``request``.

    Raises:
        UnknownFirewallError: When ``name`` names no configured firewall.
        AuthenticationError: When authentication fails and no handler answered.
        AccessDeniedError: When an access rule or a scope is not granted.
        CarriedResponse: When a success or failure handler produced a response.
    """
    context = _resolve(firewall_map, name, request)
    if context is None or not context.security:
        if scopes:
            raise AccessDeniedError(
                "A scoped resource was reached with no firewall to authenticate the caller.",
            )
        return

    setattr(request.state, FIREWALL_CONTEXT_KEY, context)
    await _authenticate_once(context, request)
    token = token_storage.get_token() or NullToken()
    setattr(request.state, TOKEN_KEY, token)
    await context.access_listener.check_access(request, token)
    if scopes:
        await _check_scopes(access_decision_manager, request, token, scopes)


def _resolve(
    firewall_map: FirewallMapInterface, name: str | None, request: Request
) -> FirewallContextInterface | None:
    """Return the firewall to run: the one named, or the first that matches."""
    if name is not None:
        return firewall_map.get(name)
    return firewall_map.match(request)


async def _authenticate_once(context: FirewallContextInterface, request: Request) -> None:
    """Authenticate the request under ``context`` at most once, memoised by name.

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
    memo: dict[str, BaseException | None] = getattr(request.state, AUTHENTICATED_FIREWALLS_KEY, {})
    if not memo:
        setattr(request.state, AUTHENTICATED_FIREWALLS_KEY, memo)
    if context.name in memo:
        recorded = memo[context.name]
        if recorded is not None:
            raise type(recorded)(str(recorded))
        return
    try:
        response = await context.authenticator_manager.authenticate_request(request)
    except BaseException as error:
        memo[context.name] = error
        raise
    else:
        memo[context.name] = None
    if response is not None:
        raise CarriedResponse(response)


async def _check_scopes(
    access_decision_manager: AccessDecisionManagerInterface,
    request: Request,
    token: TokenInterface,
    scopes: Sequence[str],
) -> None:
    """Decide the accumulated scopes against the token, denying when short.

    Raises:
        AccessDeniedError: When the token lacks a required scope, carrying the
            scope attribute so the exception listener answers with a scope
            challenge.
    """
    del request
    attribute = oauth2_scope(*scopes)
    decision = AccessDecision()
    granted = await access_decision_manager.decide(token, [attribute], access_decision=decision)
    if not granted:
        raise AccessDeniedError(
            "The token does not carry the scope this resource requires.",
            attributes=(attribute,),
            access_decision=decision,
        )
