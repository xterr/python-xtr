"""Unit tests for :class:`xtr_orm_fixtures.purger.OrmPurgerFactory`."""

from __future__ import annotations

from sqlalchemy import MetaData

from xtr_orm_fixtures.purger import OrmPurger, OrmPurgerFactory, PurgeMode


def test_factory_sets_mode_and_exclusions() -> None:
    purger = OrmPurgerFactory().create_for_connection(
        "default", MetaData(), excluded=["countries"], purge_with_truncate=True
    )

    assert isinstance(purger, OrmPurger)
    assert (purger.mode, purger.excluded) == (PurgeMode.TRUNCATE, frozenset({"countries"}))


def test_factory_deletes_and_keeps_nothing_by_default() -> None:
    purger = OrmPurgerFactory().create_for_connection("default", MetaData())

    assert isinstance(purger, OrmPurger)
    assert (purger.mode, purger.excluded) == (PurgeMode.DELETE, frozenset())
