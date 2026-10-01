"""The access map interface is a runtime-checkable protocol."""

from __future__ import annotations

from xtr_security_http.access_map import AccessMap
from xtr_security_http.access_map_interface import AccessMapInterface


def test_the_access_map_satisfies_the_interface() -> None:
    access_map = AccessMap()
    assert isinstance(access_map, AccessMapInterface)
    assert AccessMapInterface in type(access_map).__mro__


def test_a_bare_object_does_not_satisfy_the_interface() -> None:
    assert not isinstance(object(), AccessMapInterface)
