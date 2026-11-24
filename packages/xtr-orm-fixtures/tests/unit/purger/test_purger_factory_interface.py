"""Unit tests for :class:`xtr_orm_fixtures.purger.PurgerFactoryInterface`."""

from __future__ import annotations

from xtr_orm_fixtures.purger import OrmPurgerFactory, PurgerFactoryInterface


def test_the_default_factory_is_a_purger_factory() -> None:
    assert isinstance(OrmPurgerFactory(), PurgerFactoryInterface)


def test_a_class_without_create_for_connection_is_not_a_purger_factory() -> None:
    assert not isinstance(object(), PurgerFactoryInterface)
