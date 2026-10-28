"""A guard expression ties a guard to the one transition it was configured on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_workflow import Transition
from xtr_workflow.event_listener import GuardExpression

if TYPE_CHECKING:
    from xtr_workflow.event_listener import GuardContext

TRANSITION = Transition("publish", "draft", "published")


def _allow(context: GuardContext) -> bool:
    del context
    return True


def test_it_keeps_the_transition_it_guards() -> None:
    expression = GuardExpression(TRANSITION, _allow)

    assert expression.get_transition() is TRANSITION


def test_its_expression_is_the_guard_itself() -> None:
    expression = GuardExpression(TRANSITION, _allow)

    assert expression.get_expression() is _allow
