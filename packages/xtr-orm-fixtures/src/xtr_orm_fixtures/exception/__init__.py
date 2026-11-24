"""Every error this library raises, all deriving from :class:`OrmFixturesError`."""

from __future__ import annotations

from .circular_reference_error import CircularReferenceError
from .invalid_argument_error import InvalidArgumentError
from .missing_fixture_error import MissingFixtureError
from .orm_fixtures_error import OrmFixturesError
from .reference_exists_error import ReferenceExistsError
from .reference_not_found_error import ReferenceNotFoundError

__all__ = [
    "CircularReferenceError",
    "InvalidArgumentError",
    "MissingFixtureError",
    "OrmFixturesError",
    "ReferenceExistsError",
    "ReferenceNotFoundError",
]
