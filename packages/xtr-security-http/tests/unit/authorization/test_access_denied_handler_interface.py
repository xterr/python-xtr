"""The access-denied handler interface is a runtime-checkable protocol."""

from __future__ import annotations

from xtr_http_kernel.bridge import ResponseFactory

from xtr_security_http.authorization.access_denied_handler_interface import (
    AccessDeniedHandlerInterface,
)
from xtr_security_http.authorization.insufficient_scope_access_denied_handler import (
    InsufficientScopeAccessDeniedHandler,
)


def test_the_insufficient_scope_handler_satisfies_the_interface() -> None:
    assert isinstance(
        InsufficientScopeAccessDeniedHandler(ResponseFactory()),
        AccessDeniedHandlerInterface,
    )


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AccessDeniedHandlerInterface)
