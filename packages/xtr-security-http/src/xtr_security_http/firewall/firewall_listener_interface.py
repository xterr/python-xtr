"""The contract every listener of a firewall's chain implements."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["FirewallListenerInterface"]


@runtime_checkable
class FirewallListenerInterface(Protocol):
    """One step of a firewall's chain of listeners over a request.

    A firewall runs its listeners in the order the bundle sorted them —
    by :meth:`get_priority`, highest first — and each one gets the same
    two questions. :meth:`supports` is asked first, and only a listener
    that did not answer ``False`` has :meth:`authenticate` called: the
    chain skips a listener on a strict ``False`` alone, while ``None``
    and ``True`` both go on to authenticate. ``None`` is the lazy
    answer — nothing in the request's head committed this listener, but
    it still wants a say, the way a listener that only reacts once the
    token storage is read does.

    :meth:`authenticate` does the work — typically answering the
    request by setting a response on the event, which is also what
    stops the chain: a listener that answered decides the request, and
    the ones after it would be deciding about a request that has
    already been dealt with. A listener that only wants to read or
    annotate the request leaves the response alone and the chain runs
    on.

    Both hooks are async: the request-inspecting collaborators of this
    package — the access map, the request matchers, the authenticator
    manager — answer asynchronously, so a listener's questions await.

    The event is the kernel's request event, which carries the request
    as a message and the per-request state bag the security state rides
    on.
    """

    async def supports(self, request: ServerRequestInterface) -> bool | None:
        """Tell whether this listener handles ``request``.

        ``False`` skips the listener; ``None`` and ``True`` both run
        :meth:`authenticate` — ``None`` marking a listener that joins
        lazily rather than eagerly.
        """
        ...

    async def authenticate(self, request_event: RequestEvent) -> None:
        """Handle the request ``request_event`` carries.

        A listener that answers the request sets a response on the
        event, which also stops the chain; one that leaves the response
        alone lets the chain run on.
        """
        ...

    @staticmethod
    def get_priority() -> int:
        """Return this listener's position in the chain: the higher, the earlier it runs.

        The bundle's sorting pass orders a firewall's chain by this,
        highest first, keeping the registration order of listeners that
        share a priority.
        """
        ...
