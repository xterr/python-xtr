"""The fallback marker is a base class an entry point that stands in inherits."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_http_kernel.bridge import ResponseFactory

from xtr_security_http.entry_point.authentication_entry_point_interface import (
    AuthenticationEntryPointInterface,
)
from xtr_security_http.entry_point.fallback_authentication_entry_point_interface import (
    FallbackAuthenticationEntryPointInterface,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError


@final
class _StandingIn(FallbackAuthenticationEntryPointInterface):
    """An entry point that stands in, answering with a bare 401."""

    @override
    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        del request, error
        return ResponseFactory().create_response(401)


def test_a_fallback_is_an_entry_point() -> None:
    assert isinstance(_StandingIn(), AuthenticationEntryPointInterface)


def test_a_bare_object_is_no_fallback() -> None:
    assert not isinstance(object(), FallbackAuthenticationEntryPointInterface)
