"""The route-surface decorators: the firewall's authorization markers.

:class:`~xtr_security_http.decorator.is_granted.IsGranted`,
:class:`~xtr_security_http.decorator.current_user.CurrentUser`,
:class:`~xtr_security_http.decorator.current_token.CurrentToken` and
:class:`~xtr_security_http.decorator.is_csrf_token_valid.IsCsrfTokenValid`
are the markers a route carries — pure metadata, each delegating its
enforcement to an injectable service in :mod:`xtr_security_http.resolver` —
and :class:`~xtr_security_http.decorator.is_granted_context.IsGrantedContext`
is the context a closure attribute is handed.
:class:`~xtr_security_http.decorator.firewall_listener_order.FirewallListenerOrder`
declares where a firewall listener stands among the ones it shares a
priority with.
"""

from __future__ import annotations

from .current_token import CurrentToken
from .current_user import CurrentUser
from .firewall_listener_order import FirewallListenerOrder, firewall_listener_order_of
from .is_csrf_token_valid import (
    SOURCE_HEADER,
    SOURCE_PAYLOAD,
    SOURCE_QUERY,
    IsCsrfTokenValid,
)
from .is_granted import IsGranted
from .is_granted_context import IsGrantedContext

__all__ = [
    "SOURCE_HEADER",
    "SOURCE_PAYLOAD",
    "SOURCE_QUERY",
    "CurrentToken",
    "CurrentUser",
    "FirewallListenerOrder",
    "IsCsrfTokenValid",
    "IsGranted",
    "IsGrantedContext",
    "firewall_listener_order_of",
]
