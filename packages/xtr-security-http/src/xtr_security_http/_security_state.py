"""The per-request state the security layer keeps on the request's state bag.

The kernel's lifecycle events carry the request as a message and, beside it,
``state`` — the per-request bag the framework's own request wraps, one mapping
per request that every listener and the framework share. That bag is where this
layer's flow state lives: the firewall that ran, the token it authenticated,
how far authentication got. All of it gathers into one mutable object parked
on the bag under a single prefixed key, so the bag stays tidy and the shape
stays this module's to change.

Also here: the control-flow error a firewall raises to carry a handler's
response out to the exception listener.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from xtr_http_message_contracts import ResponseInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.firewall_context_interface import FirewallContextInterface

__all__ = [
    "SECURITY_STATE_KEY",
    "CarriedResponse",
    "SecurityState",
    "security_state_of",
]

#: The one key the security layer parks its state under, on the request's
#: state bag. Prefixed so it never collides with what an application keeps
#: on the same bag; the names inside the object follow the same prefix.
SECURITY_STATE_KEY: Final = "_xtr_security_"


@final
class SecurityState:
    """What the security layer learned about one request while running it.

    The firewall's glue creates this once per request — from the same bag the
    lifecycle's events carry — and everything that needs to reach a later
    step in the same request reads it back: the runner memoises
    authentication on it, and the exception listener, a singleton with no
    request scope of its own, reads the firewall context and the token off
    it to answer the request's failure.

    Attributes:
        authenticated_firewalls: Maps a firewall name to the settled outcome
            of authenticating this request under it — the exception
            authentication raised, or ``None`` for a pass that authenticated
            — so authentication stays one pass per firewall. A name is absent
            until an outcome settles, so no unfinished pass reads as
            authenticated.
        firewall_context: The firewall in charge of the request, recorded by
            the runner so the exception listener can read the entry point and
            handlers it needs without touching the container.
        token: The token the firewall authenticated for the request,
            recorded alongside the context so the exception listener can
            weigh it without the token storage.
    """

    __slots__ = ("authenticated_firewalls", "firewall_context", "token")

    def __init__(self) -> None:
        """Start with no firewall run, no token, and an empty memo."""
        self.authenticated_firewalls: dict[str, BaseException | None] = {}
        self.firewall_context: FirewallContextInterface | None = None
        self.token: TokenInterface | None = None


def security_state_of(bag: MutableMapping[str, object]) -> SecurityState:
    """Return the security state parked on ``bag``, creating it on first read.

    Whoever reads first — the glue building the state the runner takes, or
    the exception listener answering a request the firewall never ran under —
    finds the same object every later reader in the request finds, because
    the bag is one mapping per request by construction.

    Args:
        bag: The request's state bag — the same mapping the lifecycle's
            events carry as ``state`` and the framework's own request wraps.

    Returns:
        The request's security state, parked on ``bag`` if this is the first
        read.
    """
    state = bag.get(SECURITY_STATE_KEY)
    if isinstance(state, SecurityState):
        return state

    created = SecurityState()
    bag[SECURITY_STATE_KEY] = created
    return created


class CarriedResponse(Exception):  # noqa: N818 -- a control-flow carrier, not an error condition
    """Carries a response an authentication handler produced out of the firewall.

    A firewall runs as a dependency, which cannot itself answer a request; when
    a success or failure handler produced a response, the firewall raises this
    to carry it to the exception listener, which emits the response it holds.
    Internal to the HTTP layer.

    Attributes:
        response: The response to send.
    """

    response: ResponseInterface

    def __init__(self, response: ResponseInterface) -> None:
        """Record the response to carry out to the exception listener."""
        super().__init__("A security handler produced a response.")
        self.response = response
