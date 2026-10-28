"""Who hears an article being published."""

from __future__ import annotations

from typing import final

from xtr_workflow.decorator import as_transition_listener
from xtr_workflow.event import TransitionEvent


@final
class Publication:
    """Keeps every article published."""

    def __init__(self) -> None:
        self.published: list[object] = []

    @as_transition_listener("article", "publish")
    def on_publish(self, event: TransitionEvent) -> None:
        self.published.append(event.get_subject())
