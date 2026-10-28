"""A workflow type says whether a subject is in one place or in several."""

from __future__ import annotations

from xtr_workflow import WorkflowType


def test_its_members_are_the_names_configuration_uses() -> None:
    assert [member.value for member in WorkflowType] == ["state_machine", "workflow"]
