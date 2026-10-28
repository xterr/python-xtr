"""A workflow class named explicitly, taking its listeners from the shared review base."""

from __future__ import annotations

from typing import Annotated, ClassVar

from tests.fixtures.review_listeners import ReviewListeners
from xtr_workflow.decorator import Transition, as_workflow


@as_workflow(name="article")
class ArticleWorkflow(ReviewListeners):
    APPROVE: ClassVar[Annotated[str, Transition(froms="draft", tos="approved")]] = "approve"
