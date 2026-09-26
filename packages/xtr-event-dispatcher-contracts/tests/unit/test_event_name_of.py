from __future__ import annotations

from xtr_event_dispatcher_contracts import Event, event_name_of


class _Outer:
    class Inner(Event):
        pass


def test_a_string_is_its_own_name() -> None:
    assert event_name_of("order.placed") == "order.placed"


def test_a_class_stands_for_its_module_and_qualified_name() -> None:
    assert event_name_of(Event) == "xtr_event_dispatcher_contracts.event.Event"


def test_a_nested_class_keeps_its_enclosing_class_in_the_name() -> None:
    assert event_name_of(_Outer.Inner) == f"{__name__}._Outer.Inner"
