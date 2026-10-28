"""The logout listener that clears the stored cross-site request forgery tokens."""

from __future__ import annotations

from typing import final

import pytest
from xtr_security_csrf import ClearableTokenStorageInterface

from tests.support.messages import make_message
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.event_listener import CsrfTokenClearingListener

pytestmark = pytest.mark.anyio


@final
class _RecordingClearableStorage:
    """A clearable token storage that records the clears it is asked for."""

    __slots__ = ("clears",)

    def __init__(self) -> None:
        self.clears = 0

    async def get_token(self, token_id: str) -> str:
        """Answer nothing; the logout listener only clears."""
        del token_id
        raise AssertionError("the logout listener never reads a token")

    async def set_token(self, token_id: str, token: str) -> None:
        """Answer nothing; the logout listener only clears."""
        del token_id, token
        raise AssertionError("the logout listener never stores a token")

    async def remove_token(self, token_id: str) -> str | None:
        """Answer nothing; the logout listener only clears."""
        del token_id
        raise AssertionError("the logout listener never removes a token")

    async def has_token(self, token_id: str) -> bool:
        """Answer nothing; the logout listener only clears."""
        del token_id
        raise AssertionError("the logout listener never checks a token")

    async def clear(self) -> None:
        """Record the clear."""
        self.clears += 1


def test_the_recording_storage_satisfies_the_clearable_interface() -> None:
    assert isinstance(_RecordingClearableStorage(), ClearableTokenStorageInterface)


def test_it_subscribes_to_the_logout_event_at_the_default_priority() -> None:
    assert CsrfTokenClearingListener.get_subscribed_events() == {LogoutEvent: "on_logout"}


async def test_a_logout_clears_every_token_the_storage_minted() -> None:
    storage = _RecordingClearableStorage()
    listener = CsrfTokenClearingListener(storage)

    await listener.on_logout(LogoutEvent(make_message(), None))

    assert storage.clears == 1
