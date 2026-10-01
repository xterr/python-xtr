"""Authorization at the HTTP edge: scope voting and turning a denial into a response."""

from __future__ import annotations

from .access_denied_handler_interface import AccessDeniedHandlerInterface
from .insufficient_scope_access_denied_handler import InsufficientScopeAccessDeniedHandler
from .oauth2_scope_voter import OAuth2ScopeVoter, oauth2_scope, parse_oauth2_scope

__all__ = [
    "AccessDeniedHandlerInterface",
    "InsufficientScopeAccessDeniedHandler",
    "OAuth2ScopeVoter",
    "oauth2_scope",
    "parse_oauth2_scope",
]
