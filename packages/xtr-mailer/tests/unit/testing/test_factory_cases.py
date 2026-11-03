from __future__ import annotations

import dataclasses

import pytest

from xtr_mailer.testing import FactoryCases
from xtr_mailer.transport import Dsn, NullTransportFactory


def test_its_cases_are_frozen_copies() -> None:
    dsn = Dsn("null", "null")
    supports = [(dsn, True)]

    cases = FactoryCases(create_factory=NullTransportFactory, supports=supports)
    supports.clear()

    assert cases.supports == ((dsn, True),)
    assert (cases.create, cases.unsupported_scheme, cases.incomplete_dsn) == ((), (), ())
    with pytest.raises(dataclasses.FrozenInstanceError):
        # Assigning a frozen field is the refusal under test, which both checkers report.
        cases.create = ()  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]
