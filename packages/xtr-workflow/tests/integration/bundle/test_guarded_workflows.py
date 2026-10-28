"""A workflow's guards ask the security bundle about whoever is moving the subject.

The application lists the security bundle beside the workflow bundle: listing
the workflow bundle alone never brings it along.
"""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test

from tests.fixtures.subject import Subject
from xtr_workflow import TransitionBlocker, WorkflowInterface
from xtr_workflow.bundle import WorkflowBundle
from xtr_workflow.exception import LogicError

pytestmark = pytest.mark.anyio

_APPLICATION = "tests.fixtures.app_workflow_guards"


async def test_a_guard_refusing_blocks_its_transition_and_is_named_by_the_blocker() -> None:
    kernel = Kernel(_APPLICATION, env="test", debug=False)
    async with await boot_for_test(kernel) as booted:
        workflow = await booted.container.get(WorkflowInterface, "article")

        blockers = await workflow.build_transition_blocker_list(Subject(), "publish")

    [blocker] = list(blockers)
    assert blocker.get_code() == TransitionBlocker.BLOCKED_BY_EXPRESSION_GUARD_LISTENER
    assert blocker.get_parameters() == {
        "expression": "tests.fixtures.app_workflow_guards.guards.is_editor"
    }


async def test_a_guard_sees_no_token_outside_a_request() -> None:
    kernel = Kernel(_APPLICATION, env="test", debug=False)
    async with await boot_for_test(kernel) as booted:
        workflow = await booted.container.get(WorkflowInterface, "article")

        can_archive = await workflow.can(Subject(), "archive")

    assert can_archive


def test_guards_fail_the_build_when_the_application_does_not_list_the_security_bundle() -> None:
    # xtr-security is installed here: listing the workflow bundle alone still leaves it out.
    kernel = Kernel(_APPLICATION, env="test", debug=False, bundles={WorkflowBundle: {"all": True}})

    with pytest.raises(LogicError) as raised:
        _ = kernel.build()

    assert str(raised.value) == (
        'The "security" bundle is needed to be able to use the workflow guard listener: list '
        "SecurityBundle, from xtr_security.bundle, in config/bundles.py."
    )
