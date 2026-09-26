from __future__ import annotations

from typing import TYPE_CHECKING, overload

from xtr_event_dispatcher_contracts import ListenerIntrospectionInterface

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener


class _NoListeners:
    @overload
    def get_listeners(self, event_name: None = None) -> dict[str, list[Listener]]: ...

    @overload
    def get_listeners(self, event_name: str | type) -> list[Listener]: ...

    def get_listeners(
        self,
        event_name: str | type | None = None,
    ) -> dict[str, list[Listener]] | list[Listener]:
        return {} if event_name is None else []

    def get_listener_priority(self, event_name: str | type, listener: Listener) -> int | None:
        del event_name, listener
        return None

    def has_listeners(self, event_name: str | type | None = None) -> bool:
        del event_name
        return False


def test_an_object_reading_its_listeners_is_introspectable() -> None:
    introspection: ListenerIntrospectionInterface = _NoListeners()

    assert isinstance(introspection, ListenerIntrospectionInterface)


def test_a_plain_object_is_not_introspectable() -> None:
    assert not isinstance(object(), ListenerIntrospectionInterface)
