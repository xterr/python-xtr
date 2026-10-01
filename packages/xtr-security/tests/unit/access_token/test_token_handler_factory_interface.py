"""The token-handler factory interface is a runtime-checkable protocol."""

from __future__ import annotations

from xtr_security.bundle import ServiceTokenHandlerFactory, TokenHandlerFactoryInterface


def test_the_built_in_is_an_instance_of_the_interface() -> None:
    assert isinstance(ServiceTokenHandlerFactory(), TokenHandlerFactoryInterface)


def test_a_plain_object_is_not() -> None:
    assert not isinstance(object(), TokenHandlerFactoryInterface)
