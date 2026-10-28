"""The switch-user block a firewall's configuration carries.

A firewall with a switch-user block lets a caller holding the switching role
become another user for the requests that follow — by a query parameter on
any page the firewall claims, or on one dedicated path — and step back out
the same way. The block is inert data: the bundle turns it into the chain
step that switches, and the generator that renders the addresses a page
switches by.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SwitchUserConfig"]


@dataclass(frozen=True, slots=True)
class SwitchUserConfig:
    """How a firewall's callers switch to another user.

    Attributes:
        role: The role the right to switch is decided by — the caller's
            token must hold it, weighed against the target user as the
            subject, so a target who may not be switched to is never
            switched to.
        parameter: The name a request carries the user to switch to under.
        enable_csrf: Whether a switch asks for a cross-site request forgery
            token — meaningful on a stateful firewall only, where the
            session keeps the tokens.
        csrf_parameter: The name a request carries the forgery token under.
        csrf_token_id: The id the forgery token is stored under.
        path: The dedicated path a switch is asked at, or ``None`` to read
            the parameter on any page the firewall claims.
    """

    role: str = "ROLE_ALLOWED_TO_SWITCH"
    parameter: str = "_switch_user"
    enable_csrf: bool = False
    csrf_parameter: str = "_csrf_token"
    csrf_token_id: str = "switch_user"  # noqa: S105 -- the token's id, not a credential
    path: str | None = None
