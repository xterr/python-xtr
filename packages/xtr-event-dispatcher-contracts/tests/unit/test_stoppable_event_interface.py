from __future__ import annotations

from xtr_event_dispatcher_contracts import StoppableEventInterface


class _AlwaysStopped:
    def is_propagation_stopped(self) -> bool:
        return True


def test_any_object_telling_whether_it_is_stopped_is_stoppable() -> None:
    assert isinstance(_AlwaysStopped(), StoppableEventInterface)


def test_a_plain_object_is_not_stoppable() -> None:
    assert not isinstance(object(), StoppableEventInterface)
