"""Unit tests for :class:`xtr_orm_fixtures.exception.OrmFixturesError`."""

from __future__ import annotations

from xtr_orm_fixtures.exception import (
    CircularReferenceError,
    InvalidArgumentError,
    MissingFixtureError,
    OrmFixturesError,
    ReferenceExistsError,
    ReferenceNotFoundError,
)


def test_every_error_derives_from_the_package_error() -> None:
    errors = (
        CircularReferenceError(("Users", "Orders", "Users")),
        InvalidArgumentError("bad"),
        MissingFixtureError("Users", "Orders"),
        ReferenceExistsError("admin", "User"),
        ReferenceNotFoundError("admin", "User"),
    )

    assert all(isinstance(error, OrmFixturesError) for error in errors)
