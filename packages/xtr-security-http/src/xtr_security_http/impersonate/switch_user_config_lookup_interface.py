"""What answers the switch-user configuration of the firewall a request runs in."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from .switch_user_config import SwitchUserConfig

__all__ = ["SwitchUserConfigLookupInterface"]


@runtime_checkable
class SwitchUserConfigLookupInterface(Protocol):
    """Answers the switch-user configuration of the firewall a request runs in.

    The generator's one question about the world around it: how the
    firewall the request belongs to asks for a user switch — or that it
    does not ask for one at all. Kept an interface of its own, with
    nothing else on it, so whatever knows the firewalls — a bundle's
    wiring, an application's own map — can answer without the generator
    knowing how the firewalls are held, and the generator stays usable
    with no bundle behind it.
    """

    async def get_switch_user_config(
        self,
        request: ServerRequestInterface,
    ) -> SwitchUserConfig | None:
        """Return the switch-user configuration of ``request``'s firewall, or ``None``.

        A request no firewall claims answers ``None``, the same as a
        firewall configured without a switch: neither has an address to
        generate.
        """
        ...
