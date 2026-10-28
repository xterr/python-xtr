"""A starting point for a firewall listener: the default priority, and no-op hooks to override."""

from __future__ import annotations

from typing_extensions import override

from .firewall_listener_interface import FirewallListenerInterface

__all__ = ["AbstractListener"]


class AbstractListener(  # pyright: ignore[reportImplicitAbstractClass]  -- subclasses implement supports/authenticate
    FirewallListenerInterface,
):
    """The parts of a firewall listener every kind shares.

    Gives a listener the chain's default priority — ``0``, the middle
    of the road, ahead of the listeners that only clean up and behind
    the ones that authenticate — and leaves :meth:`supports` and
    :meth:`authenticate` to the subclass: no two kinds of listener
    decide the same way, so the template decides nothing for them. A
    concrete listener overrides both, and :meth:`get_priority` when
    the chain must run it somewhere else.
    """

    @staticmethod
    @override
    def get_priority() -> int:
        """Return the chain's default priority: ``0``."""
        return 0
