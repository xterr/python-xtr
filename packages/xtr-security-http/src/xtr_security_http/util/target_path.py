"""The path a login interrupts, kept on the session for the return trip.

A request that reaches a protected resource unauthenticated is about to be
sent elsewhere — a login form, a re-authentication prompt. Where it was
heading is worth keeping: once the caller has proved themselves, the flow
returns them to it. The path is kept on the session, under a key formatted
with the firewall's name, so two firewalls never overwrite each other's
return trips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_foundation.session import SessionInterface

__all__ = ["get_target_path", "remove_target_path", "save_target_path"]


def _key(firewall_name: str) -> str:
    """Return the session key the ``firewall_name`` target path lives under."""
    return SecurityRequestAttributes.TARGET_PATH.format(firewall=firewall_name)


async def save_target_path(
    session: SessionInterface,
    firewall_name: str,
    uri: str,
) -> None:
    """Set the path the caller should be returned to once they authenticate.

    Args:
        session: The request's session, where the path waits out the login.
        firewall_name: The firewall that started the authentication, so its
            return trip never overwrites another firewall's.
        uri: The URI the interrupted request was heading for.
    """
    await session.set(_key(firewall_name), uri)


async def get_target_path(session: SessionInterface, firewall_name: str) -> str | None:
    """Return the URI the caller was heading for, when one was kept.

    Args:
        session: The request's session, where the path waits out the login.
        firewall_name: The firewall that started the authentication.

    Returns:
        The saved URI, or ``None`` when this firewall kept none.
    """
    kept = await session.get(_key(firewall_name))
    return kept if isinstance(kept, str) else None


async def remove_target_path(session: SessionInterface, firewall_name: str) -> None:
    """Drop the kept path, once the caller has been returned to it.

    Args:
        session: The request's session, where the path waited out the login.
        firewall_name: The firewall that started the authentication.
    """
    _ = await session.remove(_key(firewall_name))
