"""A reason a transition cannot be applied to a subject."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .marking import Marking

__all__ = ["TransitionBlocker"]


@final
class TransitionBlocker:
    """A reason a transition cannot be applied to a subject, in words and as a code.

    The message is for a person; the code — usually a UUID — is for code
    that has to tell one reason from another without parsing the message.
    The parameters carry whatever the condition that blocked was about, so
    a reader can say more than the message does: for "the distance must be
    over 5 miles", the 5.
    """

    BLOCKED_BY_MARKING: Final[str] = "19beefc8-6b1e-4716-9d07-a39bd6d16e34"
    """The marking does not hold the tokens the transition takes."""

    BLOCKED_BY_EXPRESSION_GUARD_LISTENER: Final[str] = "326a1e9c-0c12-11e8-ba89-0ed5f89f718b"
    """A guard configured on the transition refused it."""

    UNKNOWN: Final[str] = "e8b5bbb9-5913-4b98-bfa6-65dbd228a82a"
    """A listener blocked the transition without giving a code of its own."""

    __slots__: tuple[str, ...] = ("_code", "_message", "_parameters")

    _message: str
    _code: str
    _parameters: dict[str, object]

    def __init__(
        self,
        message: str,
        code: str,
        parameters: Mapping[str, object] | None = None,
    ) -> None:
        """Give the reason ``message``, known to code as ``code``.

        Args:
            message: Why the transition is blocked, for a person.
            code: Which reason it is, for code; usually a UUID.
            parameters: The values the condition that blocked was about.
        """
        self._message = message
        self._code = code
        self._parameters = dict(parameters) if parameters is not None else {}

    @staticmethod
    def create_blocked_by_marking(marking: Marking) -> TransitionBlocker:
        """Block a transition the subject is not in the places for.

        A state machine's subject is not in the place the transition leaves;
        a workflow's lacks a token in one of the places it leaves, or enough
        of them.
        """
        return TransitionBlocker(
            "The marking does not enable the transition.",
            TransitionBlocker.BLOCKED_BY_MARKING,
            {"marking": marking},
        )

    @staticmethod
    def create_blocked_by_expression_guard_listener(expression: str) -> TransitionBlocker:
        """Block a transition its configured guard refused.

        Args:
            expression: Names the guard that refused it.
        """
        return TransitionBlocker(
            "The expression blocks the transition.",
            TransitionBlocker.BLOCKED_BY_EXPRESSION_GUARD_LISTENER,
            {"expression": expression},
        )

    @staticmethod
    def create_unknown(message: str | None = None, backtrace_frame: int = 2) -> TransitionBlocker:
        """Block a transition for a reason no code was given for.

        Without a message, the reason names the class of the guard that
        blocked, when there is one, so whoever reads it knows where to look.

        Args:
            message: Why the transition is blocked.
            backtrace_frame: How many calls up the guard is, counting this one
                as 0. The default fits a guard that called a method which
                called this, as :meth:`GuardEvent.set_blocked` does.
        """
        if message is not None:
            return TransitionBlocker(message, TransitionBlocker.UNKNOWN)

        caller = _caller_class(backtrace_frame + 1)
        if caller is not None:
            return TransitionBlocker(
                f"The transition has been blocked by a guard ({caller}).",
                TransitionBlocker.UNKNOWN,
            )

        return TransitionBlocker(
            "The transition has been blocked by a guard.", TransitionBlocker.UNKNOWN
        )

    def get_message(self) -> str:
        """Return why the transition is blocked, for a person."""
        return self._message

    def get_code(self) -> str:
        """Return which reason it is, for code."""
        return self._code

    def get_parameters(self) -> dict[str, object]:
        """Return the values the condition that blocked was about; a copy."""
        return dict(self._parameters)


def _caller_class(depth: int) -> str | None:
    """Return the qualified name of the class the call ``depth`` frames up runs in.

    A method has its class's instance as ``self``, a class method its class
    as ``cls``; a function outside a class has neither.
    """
    frame = inspect.currentframe()
    try:
        for _ in range(depth):
            if frame is None:
                break
            frame = frame.f_back
        if frame is None:
            return None

        local_names = cast("dict[str, object]", frame.f_locals)
        owner = local_names.get("cls")
        if not isinstance(owner, type):
            instance = local_names.get("self")
            if instance is None:
                return None
            owner = type(instance)
        return f"{owner.__module__}.{owner.__qualname__}"
    finally:
        # A frame refers to its locals, which would refer back to it here.
        del frame
