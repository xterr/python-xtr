"""A workflow declared on a class is named explicitly, or after the class."""

from __future__ import annotations

import pytest

from xtr_workflow.decorator._workflow_name import class_name, workflow_name
from xtr_workflow.exception import LogicError


class PullRequestStateMachine: ...


class ArticleWorkflow: ...


class HTTPRequestWorkflow: ...


class Workflow: ...


class Task2: ...


@pytest.mark.parametrize(
    ("class_", "expected"),
    [
        (PullRequestStateMachine, "pull_request"),
        (ArticleWorkflow, "article"),
        (HTTPRequestWorkflow, "http_request"),
        (Workflow, "workflow"),
        (Task2, "task2"),
    ],
)
def test_without_a_name_it_is_derived_from_the_class(class_: type, expected: str) -> None:
    assert workflow_name(None, class_) == expected


def test_a_name_given_is_kept() -> None:
    assert workflow_name("articles", ArticleWorkflow) == "articles"


def test_an_empty_name_is_refused() -> None:
    with pytest.raises(LogicError) as raised:
        _ = workflow_name("", ArticleWorkflow)

    assert str(raised.value) == (
        f'The name of the workflow defined by "{__name__}.ArticleWorkflow" cannot be empty.'
    )


def test_a_class_is_named_by_its_module_and_qualified_name() -> None:
    assert class_name(ArticleWorkflow) == f"{__name__}.ArticleWorkflow"
