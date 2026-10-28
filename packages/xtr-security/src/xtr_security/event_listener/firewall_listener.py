"""The firewall as the application's dispatcher runs it: one listener per lifecycle event.

The firewall itself — :class:`~xtr_security_http.firewall.firewall.Firewall` —
declares the events it hears and the priorities it runs at; these thin
listeners are how the bundle puts it on the main dispatcher. A listener the
dispatcher keeps lives for the application's life, while the firewall map it
runs is a service of the request — so each listener takes the map as a
per-call injection, resolved from the unit of work the request's scope opened,
and hands it to a firewall built for the call. The priorities come from the
firewall's own declaration, so what the tests pin is what runs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_dependency_injection import (
    Injected,  # noqa: TC002 -- a listener signature the container reads
)
from xtr_event_dispatcher import SubscribedEvents, as_event_listener
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- a listener signature the container reads
    EventDispatcherInterface,
)
from xtr_http_kernel import ExceptionEvent, FinishRequestEvent, RequestEvent
from xtr_security_http.firewall.firewall import Firewall
from xtr_security_http.firewall_map_interface import (  # noqa: TC002 -- a listener signature the container reads
    FirewallMapInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["answer_the_failure", "finish_the_firewall", "run_the_firewall"]

_subscribed: Mapping[str | type, SubscribedEvents] = Firewall.get_subscribed_events()
# The two phased subscriptions are (method, priority) tuples; the finish is a
# bare method name. Read here so the listeners run at the priorities the
# firewall itself declares, which its own tests pin.
_request_subscription = cast("tuple[str, int]", _subscribed[RequestEvent])
_exception_subscription = cast("tuple[str, int]", _subscribed[ExceptionEvent])


@as_event_listener(RequestEvent, priority=_request_subscription[1])
async def run_the_firewall(
    event: RequestEvent,
    name: str,
    dispatcher: EventDispatcherInterface,
    firewall_map: Injected[FirewallMapInterface],
) -> None:
    """Run the chain of the firewall that matched the request, before routing.

    Takes the name and the dispatcher besides the event, so a failure the
    chain raises is announced on the lifecycle and answered rather than
    failing the request.
    """
    await Firewall(firewall_map).on_request(event, name, dispatcher)


@as_event_listener(ExceptionEvent, priority=_exception_subscription[1])
async def answer_the_failure(
    event: ExceptionEvent,
    firewall_map: Injected[FirewallMapInterface],
) -> None:
    """Route the failure to the listener of the firewall that ran the request."""
    await Firewall(firewall_map).on_exception(event)


@as_event_listener(FinishRequestEvent)
async def finish_the_firewall(
    event: FinishRequestEvent,
    firewall_map: Injected[FirewallMapInterface],
) -> None:
    """Put away the listener the request's firewall stored on its carrier."""
    await Firewall(firewall_map).on_finish_request(event)
