"""The authentication failure handler interface is a runtime-checkable protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_security_http.authentication.authentication_failure_handler_interface import (
    AuthenticationFailureHandlerInterface,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError


class _Failure(AuthenticationFailureHandlerInterface):
    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
        del request, error
        return None


def test_a_conforming_handler_satisfies_the_interface() -> None:
    assert isinstance(_Failure(), AuthenticationFailureHandlerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AuthenticationFailureHandlerInterface)
