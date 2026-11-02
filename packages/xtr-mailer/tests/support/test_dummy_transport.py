from __future__ import annotations

import pytest
from xtr_mime import RawMessage

from tests.support.dummy_transport import DummyTransport


def test_it_is_named_after_its_host() -> None:
    assert str(DummyTransport("a")) == "dummy://a"


@pytest.mark.anyio
async def test_it_never_sends() -> None:
    with pytest.raises(AssertionError, match="never sends"):
        _ = await DummyTransport("a").send(RawMessage(b"Hi"))
