"""What a closure attribute is handed to decide access with.

The concrete context is defined in :mod:`xtr_security_core` — the closure voter
there builds it — and re-exported here so a closure the application writes next
to :class:`~xtr_security_http.decorator.is_granted.IsGranted` annotates its
parameter from the decorator surface. The core keeps the definition because the
voter that constructs it must never reach across into the HTTP edge.
"""

from __future__ import annotations

from xtr_security_core.authorization.is_granted_context import IsGrantedContext

__all__ = ["IsGrantedContext"]
