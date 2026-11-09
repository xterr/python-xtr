"""What a session keeps of a firewall's context, and what a login does to the session.

The :class:`SessionTokenSerializer` turns the security token into the JSON a
session keeps and back — the user a token carries rebuilt as its own class, or
as the :class:`SessionUser` and :class:`PasswordSessionUser` stand-ins of a
snapshot — and the :class:`SessionAuthenticationStrategy` decides what a
successful login does to the session the request reattached.
"""

from __future__ import annotations

from .password_session_user import PasswordSessionUser
from .session_authentication_strategy import SessionAuthenticationStrategy
from .session_authentication_strategy_interface import SessionAuthenticationStrategyInterface
from .session_token_serializer import SessionTokenSerializer
from .session_user import SessionUser

__all__ = [
    "PasswordSessionUser",
    "SessionAuthenticationStrategy",
    "SessionAuthenticationStrategyInterface",
    "SessionTokenSerializer",
    "SessionUser",
]
