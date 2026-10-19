"""How a firewall's user switch is asked for."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SwitchUserConfig"]


@dataclass(frozen=True, slots=True)
class SwitchUserConfig:
    """The parts of a firewall's configuration a generated switch address reads.

    The defaults are the switch listener's own, so a firewall configured
    with nothing but the switch itself generates addresses the listener
    reads back.

    Attributes:
        parameter: The name a request carries the user to switch to under.
        enable_csrf: Whether a switch asks for a cross-site request
            forgery token.
        csrf_parameter: The name a request carries the forgery token under.
        csrf_token_id: The id the forgery token is stored under.
        path: The dedicated path a switch is asked at, or ``None`` to ask
            by the parameter on any page.
    """

    parameter: str = "_switch_user"
    enable_csrf: bool = False
    csrf_parameter: str = "_csrf_token"
    csrf_token_id: str = "switch_user"  # noqa: S105 -- the default id of the switch's forgery token, not a credential
    path: str | None = None
