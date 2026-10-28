"""The guards of the application's workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xtr_workflow.event_listener import GuardContext


async def is_editor(context: GuardContext) -> bool:
    return await context.authorization_checker.is_granted("ROLE_EDITOR", context.subject)


def is_anonymous(context: GuardContext) -> bool:
    return context.token is None and context.role_names == ()
