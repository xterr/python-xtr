"""The listener order declaration: what it records, and what it leaves alone."""

from __future__ import annotations

from typing import final

from xtr_security_http.decorator.firewall_listener_order import (
    FirewallListenerOrder,
    firewall_listener_order_of,
)


@final
class NeighbourListener:
    pass


@FirewallListenerOrder(before=NeighbourListener, after="module:LaterListener")
class DeclaringListener:
    pass


@final
class QuietListener:
    pass


@final
class SubclassListener(DeclaringListener):
    pass


def test_it_records_the_declared_order_on_the_class() -> None:
    order = firewall_listener_order_of(DeclaringListener)

    assert order is not None
    assert order.before == (NeighbourListener,)
    assert order.after == ("module:LaterListener",)


def test_a_sequence_of_targets_is_kept_as_given() -> None:
    order = FirewallListenerOrder(before=(NeighbourListener, "module:OtherListener"))

    assert order.before == (NeighbourListener, "module:OtherListener")


def test_a_class_without_the_declaration_has_no_order() -> None:
    assert firewall_listener_order_of(QuietListener) is None


def test_a_subclass_does_not_inherit_the_declaration() -> None:
    assert firewall_listener_order_of(SubclassListener) is None


def test_the_decorated_class_is_returned_unchanged() -> None:
    assert FirewallListenerOrder(before=NeighbourListener)(QuietListener) is QuietListener
