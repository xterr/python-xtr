"""A state machine class named after itself, taking its listeners from the shared review base."""

from __future__ import annotations

from typing import Annotated, ClassVar, final

from tests.fixtures.review_listeners import ReviewListeners
from xtr_workflow.decorator import Transition, as_workflow


@final
@as_workflow()
class PullRequestStateMachine(ReviewListeners):
    APPROVE: ClassVar[Annotated[str, Transition(froms="draft", tos="approved")]] = "approve"
