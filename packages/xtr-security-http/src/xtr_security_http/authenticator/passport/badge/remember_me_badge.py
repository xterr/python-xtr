"""A badge asking that a remember-me cookie be considered."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .badge_interface import BadgeInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["RememberMeBadge"]


@final
class RememberMeBadge(BadgeInterface):
    """Marks an authentication as one a remember-me cookie may outlive.

    The badge's presence alone creates no cookie: the listener that checks the
    remember-me conditions enables it — when the application asks for it
    always, or the request carries the remember-me parameter — and the
    listener that responds then sets the cookie. An authenticator that already
    knows better can :meth:`enable` or :meth:`disable` it itself.

    Attributes:
        parameters: What the listener reads to decide — the parameter name,
            whether the application always wants the cookie.
    """

    __slots__ = ("_enabled", "_parameters")

    def __init__(self, parameters: Mapping[str, object] | None = None) -> None:
        """Record the parameters the remember-me conditions are checked with."""
        self._parameters: dict[str, object] = dict(parameters) if parameters is not None else {}
        self._enabled = False

    def get_parameters(self) -> dict[str, object]:
        """Return the parameters the remember-me conditions are checked with."""
        return dict(self._parameters)

    def enable(self) -> RememberMeBadge:
        """Ask for the remember-me cookie, and return self for chaining."""
        self._enabled = True
        return self

    def disable(self) -> RememberMeBadge:
        """Suppress the cookie after it was enabled, and return self for chaining."""
        self._enabled = False
        return self

    def is_enabled(self) -> bool:
        """Tell whether the remember-me cookie is wanted."""
        return self._enabled

    @override
    def is_resolved(self) -> bool:
        """Report resolved always: the badge is a note, never a condition."""
        return True
