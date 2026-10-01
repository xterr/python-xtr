"""The closure context is re-exported on the decorator surface, from the core."""

from __future__ import annotations

from xtr_security_core.authorization.is_granted_context import (
    IsGrantedContext as CoreIsGrantedContext,
)

from xtr_security_http.decorator.is_granted_context import IsGrantedContext


def test_it_re_exports_the_core_context() -> None:
    assert IsGrantedContext is CoreIsGrantedContext
