"""Declaring where a firewall listener sits among the ones it shares a priority with."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, TypeVar, final

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["FirewallListenerOrder", "firewall_listener_order_of"]

_MARKER: Final = "__xtr_firewall_listener_order__"
_T = TypeVar("_T")


@final
class FirewallListenerOrder:
    """Declares the firewall listeners a listener runs before or after.

    Used on a listener class::

        @FirewallListenerOrder(after=ContextListener, before=AccessListener)
        class TwoFactorListener(AbstractListener): ...

    A listener's ``get_priority()`` is kept: these constraints only
    reorder the listeners that share it, and one that would need a
    listener to cross a priority fails the build instead of silently
    moving it. This way a listener cannot displace the chain's own
    ordering by mistake — it can only settle how it stands against the
    ones it runs beside.

    A target is a listener class, its ``"module:Class"`` name, or the
    qualifier it runs under in the firewall's chain. One naming a
    listener that is not in the chain is ignored — the package adding
    it may simply not be installed.
    """

    __slots__ = ("_after", "_before")

    def __init__(
        self,
        *,
        before: type | str | Sequence[type | str] = (),
        after: type | str | Sequence[type | str] = (),
    ) -> None:
        """Declare the neighbours, a single target or a sequence of them per direction."""
        self._before = _normalized(before)
        self._after = _normalized(after)

    @property
    def before(self) -> tuple[type | str, ...]:
        """Return the listeners this one runs before, as classes, names or qualifiers."""
        return self._before

    @property
    def after(self) -> tuple[type | str, ...]:
        """Return the listeners this one runs after, as classes, names or qualifiers."""
        return self._after

    def __call__(self, listener_class: type[_T]) -> type[_T]:
        """Record this order on ``listener_class`` and return it unchanged."""
        setattr(listener_class, _MARKER, self)
        return listener_class


def firewall_listener_order_of(listener_class: type) -> FirewallListenerOrder | None:
    """Return what ``@FirewallListenerOrder`` recorded on ``listener_class``, or ``None``.

    Only the class's own declaration is read: a subclass states its
    place in the chain itself, or inherits none.
    """
    return vars(listener_class).get(_MARKER)


def _normalized(targets: type | str | Sequence[type | str]) -> tuple[type | str, ...]:
    """Return ``targets`` as a tuple, wrapping a lone class or name."""
    if isinstance(targets, type | str):
        return (targets,)
    return tuple(targets)
