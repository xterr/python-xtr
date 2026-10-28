"""An audited workflow logs each move of its subjects on the ``workflow`` channel."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test

from tests.fixtures.app_workflow_audit.config.packages.logging import CAPTURED
from tests.fixtures.subject import Subject
from xtr_workflow import WorkflowInterface

pytestmark = pytest.mark.anyio

_APPLICATION = "tests.fixtures.app_workflow_audit"


async def test_each_move_of_an_audited_workflow_is_logged_once() -> None:
    CAPTURED.clear()
    kernel = Kernel(_APPLICATION, env="test", debug=False)
    async with await boot_for_test(kernel) as booted:
        article = await booted.container.get(WorkflowInterface, "article")
        silent = await booted.container.get(WorkflowInterface, "silent")

        _ = await article.apply(Subject(), "publish")
        _ = await silent.apply(Subject(), "publish")

    subject = "tests.fixtures.subject.Subject"
    records = [record for handler in CAPTURED for record in handler.records]
    assert [(record.channel, record.message) for record in records] == [
        ("workflow", f'Leaving "draft" for subject of class "{subject}" in workflow "article".'),
        (
            "workflow",
            f'Transition "publish" for subject of class "{subject}" in workflow "article".',
        ),
        (
            "workflow",
            f'Entering "published" for subject of class "{subject}" in workflow "article".',
        ),
    ]
