"""A transition could not be applied to a subject."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .logic_error import LogicError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Protocol

    # A protocol of its own rather than the workflow interface, which no
    # module of this package declares yet.
    class NamedWorkflow(Protocol):
        """The workflow a transition error was raised for, as far as the errors read it.

        They quote its name in their message and hand the workflow back to
        whoever catches them; they read nothing else from it.
        """

        def get_name(self) -> str:
            """Return the name the error's message quotes."""
            ...


__all__ = ["TransitionError"]


class TransitionError(LogicError):
    """A transition could not be applied to a subject.

    It keeps what the call was given — the subject, the transition's name, the
    workflow and the context — so whoever catches it can say which object was
    refused which move, by which workflow, without having kept them aside.
    """

    _subject: object
    _transition_name: str
    _workflow: NamedWorkflow
    _context: dict[str, object]

    def __init__(
        self,
        subject: object,
        transition_name: str,
        workflow: NamedWorkflow,
        message: str,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Record the call that failed and why.

        Args:
            subject: The object the transition was to move.
            transition_name: The name of the transition.
            workflow: The workflow the transition was applied through.
            message: Why the transition could not be applied.
            context: The context the call was given.
        """
        super().__init__(message)
        self._subject = subject
        self._transition_name = transition_name
        self._workflow = workflow
        self._context = dict(context) if context is not None else {}

    def get_subject(self) -> object:
        """Return the object the transition was to move."""
        return self._subject

    def get_transition_name(self) -> str:
        """Return the name of the transition that could not be applied."""
        return self._transition_name

    def get_workflow(self) -> NamedWorkflow:
        """Return the workflow the transition was applied through."""
        return self._workflow

    def get_context(self) -> dict[str, object]:
        """Return the context the call was given, empty when it had none."""
        return self._context
