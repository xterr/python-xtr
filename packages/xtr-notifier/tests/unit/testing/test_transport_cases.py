from __future__ import annotations

import dataclasses

import pytest

from xtr_notifier.message import ChatMessage, MessageInterface
from xtr_notifier.testing import TransportCases
from xtr_notifier.transport import NullTransport


def test_its_cases_are_frozen_copies() -> None:
    supported: list[MessageInterface] = [ChatMessage("Hello")]
    transport = NullTransport()

    cases = TransportCases(
        create_transport=lambda: pytest.fail("never built"),
        to_string=[("null", transport)],
        supported=supported,
    )
    supported.clear()

    assert cases.supported == (ChatMessage("Hello"),)
    assert cases.to_string == (("null", transport),)
    assert cases.unsupported == ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        # Assigning a frozen field is the refusal under test, which both checkers report.
        cases.supported = ()  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]
