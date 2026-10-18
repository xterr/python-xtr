"""A firewall chain was asked about a request carrying no state bag."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

__all__ = ["MissingStateBagError"]


class MissingStateBagError(SecurityError, RuntimeError):
    """A listener was asked to support a request that carries no state bag.

    The caller that runs a firewall's chain parks the kernel event's state
    bag on the request it hands to each listener's ``supports``, so a
    listener that needs the flow's per-request carrier reaches the one the
    event carries. A request without one reached the chain through a caller
    that skipped that step, and the listener refuses to guess: a silently
    fresh carrier would park the flow's handoffs where the event's readers
    never find them. Also a :class:`RuntimeError`.
    """
