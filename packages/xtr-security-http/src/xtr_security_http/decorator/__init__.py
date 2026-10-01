"""The route-surface decorators: the firewall's authorization markers.

:class:`~xtr_security_http.decorator.is_granted.IsGranted` and
:class:`~xtr_security_http.decorator.current_user.CurrentUser` are the markers a
route carries, and
:class:`~xtr_security_http.decorator.is_granted_context.IsGrantedContext` is the
context a closure attribute is handed.
"""

from __future__ import annotations

from .current_user import CurrentUser
from .is_granted import IsGranted
from .is_granted_context import IsGrantedContext

__all__ = ["CurrentUser", "IsGranted", "IsGrantedContext"]
