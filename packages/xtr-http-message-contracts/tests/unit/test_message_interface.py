from __future__ import annotations

import pytest

from tests.support.fake_message import FakeMessage
from tests.support.missing_member import members_of, without
from xtr_http_message_contracts import MessageInterface


def test_a_fake_carrying_every_member_is_a_message() -> None:
    message: MessageInterface = FakeMessage()

    assert isinstance(message, MessageInterface)


@pytest.mark.parametrize("missing", sorted(members_of(FakeMessage)))
def test_a_fake_missing_a_member_is_not_a_message(missing: str) -> None:
    assert not isinstance(without(FakeMessage, missing)(), MessageInterface)


def test_a_plain_object_is_not_a_message() -> None:
    assert not isinstance(object(), MessageInterface)
