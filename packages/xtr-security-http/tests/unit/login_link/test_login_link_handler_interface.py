"""The login-link handler interface is a runtime-checkable protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_security_http.login_link import LoginLinkHandlerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http.login_link.login_link_details import LoginLinkDetails


class _Handler(LoginLinkHandlerInterface):
    @override
    async def create_login_link(
        self,
        user: UserInterface,
        request: ServerRequestInterface | None = None,
        lifetime: int | None = None,
        parameters: Mapping[str, str | bool | int | float] | None = None,
    ) -> LoginLinkDetails:
        del user, request, lifetime, parameters
        raise NotImplementedError

    @override
    async def consume_login_link(self, request: ServerRequestInterface) -> UserInterface:
        del request
        raise NotImplementedError


def test_a_conforming_handler_satisfies_the_interface() -> None:
    assert isinstance(_Handler(), LoginLinkHandlerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), LoginLinkHandlerInterface)
