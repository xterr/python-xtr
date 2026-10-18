"""The per-request state the security layer keeps on the request's state bag.

The kernel's lifecycle events carry the request as a message and, beside it,
``state`` — the per-request bag the framework's own request wraps, one mapping
per request that every listener and the framework share. That bag is where this
layer's flow state lives: the firewall that ran, the token it authenticated,
how far authentication got. All of it gathers into one mutable object parked
on the bag under a single prefixed key, so the bag stays tidy and the shape
stays this module's to change.

Also here: the reader that hands a chain's caller the bag a listener's
``supports`` reaches.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, cast, final

from xtr_security_http.exception import MissingStateBagError
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.firewall_context_interface import FirewallContextInterface

__all__ = [
    "SecurityState",
    "security_state_of",
    "state_bag_of",
]


@final
class SecurityState:
    """What the security layer learned about one request while running it.

    The firewall creates this once per request — from the same bag the
    lifecycle's events carry — and everything that needs to reach a later
    step in the same request reads it back: the chain's steps hand each other
    what they matched and decided, and the exception listener, a singleton
    with no request scope of its own, reads the firewall context and the
    token off it to answer the request's failure.

    Attributes:
        attributes: The values the flow's steps hand each other over one
            request, keyed by the
            :class:`~xtr_security_http.security_request_attributes.SecurityRequestAttributes`
            keys — the authenticators a supports pass chose and the ones it
            skipped, the attributes an access rule matched, the cookie a
            handler staged before a response existed. Born empty with the
            carrier and never outliving the request's bag, so nothing one
            request parked leaks into the next.
        authenticated_firewalls: Maps a firewall name to the settled outcome
            of authenticating this request under it — ``None`` for a pass
            that finished, the exception for one that crashed — so
            authentication stays one pass per firewall. An authentication
            failure finishes like a pass, leaving no token; only a crash is
            recorded, and re-raised by every later call. A name is absent
            until an outcome settles, so no unfinished pass reads as
            authenticated.
        firewall_context: The firewall in charge of the request, recorded by
            the firewall so the exception listener can read the entry point
            and handlers it needs without touching the container.
        token: The token the firewall authenticated for the request,
            recorded by the chain's access step — the step that read it —
            so the exception listener can weigh a denial without the token
            storage.
    """

    __slots__ = ("attributes", "authenticated_firewalls", "firewall_context", "token")

    def __init__(self) -> None:
        """Start with no firewall run, no token, and an empty memo."""
        self.attributes: dict[str, object] = {}
        self.authenticated_firewalls: dict[str, BaseException | None] = {}
        self.firewall_context: FirewallContextInterface | None = None
        self.token: TokenInterface | None = None


def security_state_of(bag: MutableMapping[str, object]) -> SecurityState:
    """Return the security state parked on ``bag``, creating it on first read.

    Whoever reads first — the firewall matching the request, or the
    exception listener answering a request no firewall claims — finds the
    same object every later reader in the request finds, because the bag is
    one mapping per request by construction.

    Args:
        bag: The request's state bag — the same mapping the lifecycle's
            events carry as ``state`` and the framework's own request wraps.

    Returns:
        The request's security state, parked on ``bag`` if this is the first
        read.
    """
    state = bag.get(SecurityRequestAttributes.SECURITY_STATE)
    if isinstance(state, SecurityState):
        return state

    created = SecurityState()
    bag[SecurityRequestAttributes.SECURITY_STATE] = created
    return created


def state_bag_of(request: ServerRequestInterface) -> MutableMapping[str, object]:
    """Return the state bag the chain's caller parked on ``request``.

    A firewall's chain is asked about a request before it is handed the
    event: ``supports`` sees the request alone, while the state the flow
    keeps rides the event's bag. The caller that runs the chain parks that
    bag on the request it asks about — under
    :attr:`~xtr_security_http.security_request_attributes.SecurityRequestAttributes.STATE_BAG`
    — so both hooks of a listener reach one carrier per request:
    ``supports`` reads it here, ``authenticate`` reads the event's own.

    Args:
        request: The request the chain's caller is asking about.

    Returns:
        The bag the event carries, as parked on ``request``.

    Raises:
        MissingStateBagError: When the request carries no state bag — a
            caller that runs a firewall's chain without parking the event's
            bag on the request it asks about.
    """
    bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
    if not isinstance(bag, MutableMapping):
        raise MissingStateBagError(
            "The request carries no state bag: the caller running the firewall's "
            "chain must park the kernel event's state bag on the request it hands "
            "to the chain's listeners.",
        )
    return cast("MutableMapping[str, object]", bag)
