"""A definition breaks a rule of the workflow type meant to run it."""

from __future__ import annotations

from .logic_error import LogicError

__all__ = ["InvalidDefinitionError"]


class InvalidDefinitionError(LogicError):
    """A definition breaks a rule of the workflow type meant to run it.

    Raised by a definition validator: a state machine's transition leaving
    from two places, two transitions of one name leaving the same place. A
    validator checks a definition before a workflow runs it, so the mistake
    shows where the definition is made rather than halfway through a move.
    """
