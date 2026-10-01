from __future__ import annotations

from xtr_security.bundle import firewall_dispatcher_name


def test_each_firewall_has_a_dispatcher_name_of_its_own() -> None:
    assert firewall_dispatcher_name("api") == "security.event_dispatcher.api"
    assert firewall_dispatcher_name("api") != firewall_dispatcher_name("admin")
