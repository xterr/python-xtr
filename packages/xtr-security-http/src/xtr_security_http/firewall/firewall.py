"""The firewall: a subscriber over the request lifecycle's events.

This is the one firewall an application runs. The security bundle — the
``xtr-security`` package — registers it on the kernel lifecycle's main
dispatcher, and every request the lifecycle announces reaches the firewall
that matched it, before routing: a request no route would answer is still
challenged as a request, not answered as a 404.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_http_kernel import ExceptionEvent, FinishRequestEvent, RequestEvent

from xtr_security_http._security_state import security_state_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .exception_listener import ExceptionListener

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_event_dispatcher_contracts import EventDispatcherInterface

    from xtr_security_http.firewall_map_interface import FirewallMapInterface

    from .firewall_listener_interface import FirewallListenerInterface

__all__ = ["Firewall"]

# The request phase runs after the framework's own request listeners have
# settled what the request is known by — the unit of work opens at 8192 and
# the request id at 4096, on the same higher-first scale — and ahead of the
# default-priority listeners. The exception phase routes to the request's
# stored listener ahead of the listeners that only observe the failure.
_REQUEST_PRIORITY: Final = 8
_EXCEPTION_PRIORITY: Final = 1


@final
class Firewall(EventSubscriberInterface):
    """Runs the firewall a request matched over the request lifecycle's events.

    At the request: the map is asked which firewall claims the request, and
    that firewall's chain is run in the order the bundle's sorting pass left
    it in. Each step is asked first — only a strict ``False`` skips it;
    ``None`` and ``True`` both go on — and a step that answered the request
    ends the chain: the steps after it would be deciding about a request
    already dealt with. The logout listener, when the firewall has one, is
    inserted ahead of the first step running at a lower priority, so a
    logout is handled before the steps that would only clean up after it.

    The matched firewall is parked on the request's security state — the
    per-request carrier — so a failure of the request reaches the entry
    point and the handlers of the firewall that ran it, and its exception
    listener is parked there for the exception phase, which routes the
    request's failure to the listener of the firewall that ran it; the
    finish phase puts the reference away. The carrier is one object per
    request, so nothing one request parked reaches another.

    A failure the chain raises at the request is announced on the same
    lifecycle: the exception event is dispatched, and whichever listener
    answers it — the matched firewall's stored listener first, the
    listeners that only observe the failure after it — has its response
    set on the request's event, so the request is answered rather than
    failing. A caller driving the events by hand, with no dispatcher
    handed to ``on_request``, sees the failure raise as it was raised.

    The kernel has one lifecycle per request — no request is handled inside
    another — so the main-request-only guard the upstream subscriber opens
    with has nothing to guard here.

    A step's ``supports`` is asked about the request alone, while the state
    the flow keeps rides the event's bag: the request handed to it carries
    that bag, parked under
    :attr:`~xtr_security_http.security_request_attributes.SecurityRequestAttributes.STATE_BAG`,
    so both hooks of a step reach one carrier per request.
    """

    __slots__ = ("_firewall_map",)

    def __init__(self, firewall_map: FirewallMapInterface) -> None:
        """Build the firewall over the application's firewalls.

        Args:
            firewall_map: Answers a request with the firewall that matched
                it — its chain, its exception listener and its logout
                listener.
        """
        self._firewall_map = firewall_map

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to the request, the exception and the finish of every request."""
        return {
            RequestEvent: ("on_request", _REQUEST_PRIORITY),
            ExceptionEvent: ("on_exception", _EXCEPTION_PRIORITY),
            FinishRequestEvent: "on_finish_request",
        }

    async def on_request(
        self,
        event: RequestEvent,
        name: str | None = None,
        dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Run the chain of the firewall that matched the event's request.

        A request no firewall claims runs nothing: no chain, nothing parked,
        so a failure of such a request is answered by whatever else handles
        it. An open firewall — one configured ``security=False`` — runs its
        chain but parks no context: it authenticates nothing, so there is no
        entry point of its own to answer with.

        Args:
            event: The request the lifecycle announced.
            name: The name the event was dispatched under; unused.
            dispatcher: Where a failure the chain raises is announced. The
                dispatcher passes itself; a caller driving the events by
                hand leaves it out and sees the failure raise.
        """
        del name
        context = await self._firewall_map.match(event.request)
        if context is None:
            return
        state = security_state_of(event.state)
        if context.security:
            state.firewall_context = context
        if context.exception_listener is not None:
            state.attributes[SecurityRequestAttributes.EXCEPTION_LISTENER] = (
                context.exception_listener
            )
        asked = event.request.with_attribute(SecurityRequestAttributes.STATE_BAG, event.state)
        try:
            for step in _chain_with_logout(context.listeners, context.logout_listener):
                if await step.supports(asked) is False:
                    continue
                await step.authenticate(event)
                if event.response is not None:
                    break
        except Exception as error:
            if dispatcher is None:
                raise
            failure = ExceptionEvent(event.request, event.state, error)
            _ = await dispatcher.dispatch(failure)
            if failure.response is not None:
                event.set_response(failure.response)

    async def on_exception(self, event: ExceptionEvent) -> None:
        """Route the failure to the listener of the firewall that ran the request.

        A request whose firewall stored no listener — none matched it, or
        the failure predates the request phase — is left to whatever else
        handles the failure.
        """
        parked = security_state_of(event.state).attributes.get(
            SecurityRequestAttributes.EXCEPTION_LISTENER,
        )
        if isinstance(parked, ExceptionListener):
            await parked.on_exception(event)

    async def on_finish_request(self, event: FinishRequestEvent) -> None:
        """Put away the listener the request's firewall stored.

        The carrier does not outlive the request's bag; this frees the
        listener reference at the moment the request is done with it, which
        is what the finish of a request is for.
        """
        _ = security_state_of(event.state).attributes.pop(
            SecurityRequestAttributes.EXCEPTION_LISTENER, None
        )


def _chain_with_logout(
    chain: tuple[FirewallListenerInterface, ...],
    logout_listener: FirewallListenerInterface | None,
) -> Iterator[FirewallListenerInterface]:
    """Yield ``chain`` with ``logout_listener`` inserted where it runs.

    The logout step joins ahead of the first chain step running at a lower
    priority than its own — a logout is handled before the steps that would
    only clean up after it — and at the end when no step runs lower, so a
    chain without it is yielded untouched.
    """
    if logout_listener is None:
        yield from chain
        return
    logout_priority = logout_listener.get_priority()
    pending = logout_listener
    for step in chain:
        if pending is not None and step.get_priority() < logout_priority:
            yield pending
            pending = None
        yield step
    if pending is not None:
        yield pending
