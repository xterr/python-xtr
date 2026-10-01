"""The authentication success handler interface is a runtime-checkable protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_security_http.authentication.authentication_success_handler_interface import (
    AuthenticationSuccessHandlerInterface,
)

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_security_core.authentication.token.token_interface import TokenInterface


class _Success(AuthenticationSuccessHandlerInterface):
    @override
    async def on_authentication_success(
        self,
        request: Request,
        token: TokenInterface,
        firewall_name: str,
    ) -> Response | None:
        del request, token, firewall_name
        return None


def test_a_conforming_handler_satisfies_the_interface() -> None:
    assert isinstance(_Success(), AuthenticationSuccessHandlerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AuthenticationSuccessHandlerInterface)
