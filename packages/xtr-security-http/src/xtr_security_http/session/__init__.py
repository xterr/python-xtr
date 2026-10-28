"""What a successful login does to the session the request reattached."""

from __future__ import annotations

from .session_authentication_strategy import SessionAuthenticationStrategy
from .session_authentication_strategy_interface import SessionAuthenticationStrategyInterface

__all__ = [
    "SessionAuthenticationStrategy",
    "SessionAuthenticationStrategyInterface",
]
