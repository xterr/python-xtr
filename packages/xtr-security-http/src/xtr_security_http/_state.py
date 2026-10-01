"""The keys the firewall stashes its per-request state on ``request.state`` under.

Authentication runs once per request; the firewall that ran and the token it
authenticated are stashed here for the dependencies and the exception listener
that read them later in the same request. Every key is prefixed so it never
collides with what an application keeps on the same object.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from starlette.responses import Response

__all__ = [
    "AUTHENTICATED_FIREWALLS_KEY",
    "FIREWALL_CONTEXT_KEY",
    "TOKEN_KEY",
    "CarriedResponse",
]

_PREFIX: Final = "_xtr_security_"

#: Maps a firewall name to the outcome of authenticating this request under it —
#: the error authentication raised, or ``None`` for a plain success — so
#: authentication stays one pass per firewall.
AUTHENTICATED_FIREWALLS_KEY: Final = f"{_PREFIX}authenticated_firewalls"

#: The firewall context in charge of the request, stashed by the firewall so the
#: exception listener — a singleton with no access to the request scope — reads
#: the entry point and handlers it needs without touching the container.
FIREWALL_CONTEXT_KEY: Final = f"{_PREFIX}firewall_context"

#: The token the firewall authenticated for the request, stashed alongside the
#: context so the exception listener can weigh it without the token storage.
TOKEN_KEY: Final = f"{_PREFIX}token"


class CarriedResponse(Exception):  # noqa: N818 -- a control-flow carrier, not an error condition
    """Carries a response an authentication handler produced out of the firewall.

    A firewall runs as a dependency, which cannot itself answer a request; when
    a success or failure handler produced a response, the firewall raises this
    to carry it to the exception listener, which emits the response it holds.
    Internal to the HTTP layer.

    Attributes:
        response: The response to send.
    """

    response: Response

    def __init__(self, response: Response) -> None:
        """Record the response to carry out to the exception listener."""
        super().__init__("A security handler produced a response.")
        self.response = response
