"""A guard tied to the one transition it was configured on."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_workflow.transition import Transition

    from .guard_context import GuardContext

__all__ = ["GuardExpression"]


@final
class GuardExpression:
    """A guard, and the transition it guards among those sharing a name.

    A state machine has one transition per pair of places a name moves
    between, and every one of them is guarded under the same event name;
    keeping the transition lets the guard listener run each guard for the
    transition it was configured on only.
    """

    __slots__: tuple[str, ...] = ("_guard", "_transition")

    _transition: Transition
    _guard: Callable[[GuardContext], bool | Awaitable[bool]]

    def __init__(
        self,
        transition: Transition,
        guard: Callable[[GuardContext], bool | Awaitable[bool]],
    ) -> None:
        """Guard ``transition`` with ``guard``.

        Args:
            transition: The transition, by identity.
            guard: Called with the guard context; the transition may run only
                when it answers true, at once or through an awaitable.
        """
        self._transition = transition
        self._guard = guard

    def get_transition(self) -> Transition:
        """Return the transition guarded."""
        return self._transition

    def get_expression(self) -> Callable[[GuardContext], bool | Awaitable[bool]]:
        """Return the guard: the callable deciding whether the transition may run."""
        return self._guard
