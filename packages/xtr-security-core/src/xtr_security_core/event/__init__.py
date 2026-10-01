"""The events this library dispatches."""

from __future__ import annotations

from .authentication_event import AuthenticationEvent
from .authentication_success_event import AuthenticationSuccessEvent
from .vote_event import VoteEvent

__all__ = ["AuthenticationEvent", "AuthenticationSuccessEvent", "VoteEvent"]
