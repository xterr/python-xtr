from __future__ import annotations

import dataclasses

import pytest

from xtr_notifier.testing import FactoryCases
from xtr_notifier.transport import NullTransportFactory


def test_its_cases_are_frozen_copies() -> None:
    supports = [(True, "null://null")]

    cases = FactoryCases(
        create_factory=NullTransportFactory,
        supports=supports,
        unsupported_scheme=[("foo://default", None)],
    )
    supports.clear()

    assert cases.supports == ((True, "null://null"),)
    assert cases.unsupported_scheme == (("foo://default", None),)
    assert cases.create == ()
    assert cases.incomplete_dsn == ()
    assert cases.missing_required_option == ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        # Assigning a frozen field is the refusal under test, which both checkers report.
        cases.create = ()  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]
