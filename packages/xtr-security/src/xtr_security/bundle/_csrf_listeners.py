"""The forgery-token listeners: the request's park, and the per-call checks.

A dispatcher keeps its listeners for the application's life, so a listener
service must be a singleton — and a singleton cannot hold what belongs to one
request. These listeners are functions instead: the container fills their
injected parameters on every call, from the unit of work the request's scope
opened, so the manager and the storage they read are the request's own —
the same way the firewall's own runner takes the map it runs. Each wraps the
landed listener class it answers for, built for the call.

The module is loaded only when a firewall's configuration asks for a forgery
token, so its one dispatcher listener — the park of the request, ahead of the
firewall — joins only an application that asked for the machinery.
"""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003 -- annotations the container reads at runtime
from typing import TYPE_CHECKING, Annotated, cast, final

from xtr_dependency_injection import Injected, Target, bind_callable
from xtr_event_dispatcher import as_event_listener
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- annotations the container reads at runtime
    Listener,
)
from xtr_http_kernel import RequestEvent
from xtr_security_csrf.csrf_token_manager_interface import (
    CsrfTokenManagerInterface,  # noqa: TC002 -- annotations the container reads at runtime
)
from xtr_security_csrf.token_storage.clearable_token_storage_interface import (
    ClearableTokenStorageInterface,  # noqa: TC002 -- annotations the container reads at runtime
)
from xtr_security_http import (
    CheckPassportEvent,
    CsrfProtectionListener,
    CsrfTokenClearingListener,
    LoginSuccessEvent,
    LogoutEvent,
    SessionStrategyListener,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes
from xtr_security_http.session.session_authentication_strategy import (
    SessionAuthenticationStrategy,
)

from xtr_security.bundle._csrf_wiring import (  # noqa: TC001 -- an annotation the container reads at runtime
    ParkedRequest,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from xtr_service_contracts import ContainerInterface

__all__ = [
    "PerCallListener",
    "check_the_passport_token",
    "clear_csrf_tokens_on_logout",
    "park_the_request",
    "session_strategy_listener",
]


# Ahead of the firewall (8), behind the router (32): the request is the one
# the lifecycle carries, and the firewall has not run yet.
_PARK_PRIORITY = 16


@final
class PerCallListener:
    """One function listener, its container-filled parameters resolved per call.

    What a dispatcher's compiled listener map holds in place of this is a
    reference it can turn into a listener once built; this one binds the
    function to the container at that moment, and the binding fills the
    function's injected parameters on every call — so a scoped service the
    function asks for is the one of the request the call runs in, never the
    first request's kept for every later one.
    """

    __slots__ = ("_function",)

    def __init__(self, function: Callable[..., Awaitable[None]]) -> None:
        """Hold the function the dispatcher will call per event."""
        self._function = function

    def listener(self, container: ContainerInterface) -> Listener:
        """Return the listener calling the function, its injections filled per call."""
        bound = bind_callable(container, self._function)

        async def listener(*arguments: object) -> None:
            _ = await bound(arguments[0])

        for attribute in ("__module__", "__name__", "__qualname__"):
            setattr(listener, attribute, getattr(self._function, attribute))
        return cast("Listener", listener)


@as_event_listener(RequestEvent, priority=_PARK_PRIORITY)
async def park_the_request(
    event: RequestEvent,
    request_park: Injected[ParkedRequest],
) -> None:
    """Park the request where the chain's built services read it from.

    The chain's steps hand each other the request as an argument; the
    services they hold at construction see only what this parks here. The
    bag is the event's own state — the same mapping every listener of the
    request shares — parked on the message the way the chain's caller parks
    it, so the session the context listener reattached reads back through
    the park exactly as it reads through the argument.
    """
    request_park.request = event.request.with_attribute(
        SecurityRequestAttributes.STATE_BAG, event.state
    )


async def check_the_passport_token(
    event: CheckPassportEvent,
    csrf_token_manager: Injected[CsrfTokenManagerInterface],
) -> None:
    """Settle the forgery badge a passport carries, ahead of any user load."""
    await CsrfProtectionListener(csrf_token_manager).check_passport(event)


async def clear_csrf_tokens_on_logout(
    event: LogoutEvent,
    csrf_token_storage: Injected[ClearableTokenStorageInterface],
) -> None:
    """Drop every forgery token the logging-out request's session minted."""
    await CsrfTokenClearingListener(csrf_token_storage).on_logout(event)


def session_strategy_listener(strategy_qualifier: str) -> Callable[..., Awaitable[None]]:
    """Return the login-success listener handing the session to its firewall's strategy.

    The strategy is the firewall's own service, qualified by its name, so the
    listener is built per firewall: the closure carries the qualifier into
    the annotation the container reads, and resolves the strategy — a service
    of the request, holding the request's clearable storage — on every login.
    """

    async def apply_the_session_strategy(event: LoginSuccessEvent, strategy: object) -> None:
        await SessionStrategyListener(
            cast("SessionAuthenticationStrategy", strategy)
        ).on_login_success(event)

    apply_the_session_strategy.__annotations__ = {
        "event": LoginSuccessEvent,
        "strategy": Annotated[SessionAuthenticationStrategy, Target(strategy_qualifier)],
        "return": None,
    }
    return apply_the_session_strategy
