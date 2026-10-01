"""The firewall-map contract the runner resolves a request's firewall through."""

from __future__ import annotations

from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.firewall_map_interface import FirewallMapInterface


def test_the_concrete_map_has_the_interface_in_its_mro() -> None:
    assert FirewallMapInterface in FirewallMap.__mro__


def test_the_interface_is_runtime_checkable() -> None:
    assert isinstance(FirewallMap(()), FirewallMapInterface)
