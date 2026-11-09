"""A login that leaves the user's load to the firewall: no loader, no upgrader of its own.

The built-in logins hand the badge their own provider's loader and the
upgrade badge its upgrader, so the firewall's user loading never runs for
them. This one names the user and its password only — read off two headers —
so the firewall's per-call listener is what gives the badge its loader, and the
password migration finds the upgrader through that loader alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_http_message_contracts.factory import ResponseFactoryInterface
from xtr_security_core import UsernamePasswordToken
from xtr_security_http import Passport, PasswordCredentials, UserBadge

from xtr_security.bundle import AuthenticatorFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError

__all__ = ["LoaderlessAuthenticator", "LoaderlessLoginConfig", "LoaderlessLoginFactory"]

_USERNAME_HEADER = "x-username"
_PASSWORD_HEADER = "x-password"


@dataclass(frozen=True, slots=True)
class LoaderlessLoginConfig:
    """The configuration the loaderless login is built from: nothing to set."""


@final
class LoaderlessAuthenticator:
    """Reads a username and a password off the request's headers into a bare passport."""

    __slots__ = ("_responses",)

    def __init__(self, responses: ResponseFactoryInterface) -> None:
        self._responses = responses

    def supports(self, request: ServerRequestInterface) -> bool | None:
        """Handle a request naming a user."""
        return request.has_header(_USERNAME_HEADER)

    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Name the user and its password, and nothing else."""
        return Passport(
            UserBadge(request.get_header_line(_USERNAME_HEADER)),
            PasswordCredentials(request.get_header_line(_PASSWORD_HEADER)),
        )

    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build the token for the user the firewall loaded."""
        user = await passport.get_user()
        return UsernamePasswordToken(user, firewall_name, user.get_roles())

    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
        firewall_name: str,
    ) -> ResponseInterface | None:
        """Let the request reach its route."""
        del request, token, firewall_name

    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
        """Refuse the request."""
        del request, error
        return self._responses.create_response(401)


@final
class LoaderlessLoginFactory(AuthenticatorFactoryInterface):
    """Builds the loaderless login; registered through the authenticator seam."""

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        return "loaderless_login"

    @property
    @override
    def priority(self) -> int:
        return 0

    @property
    @override
    def config_type(self) -> type:
        return LoaderlessLoginConfig

    @override
    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        del builder, config, user_provider

        def loaderless_authenticator(
            responses: ResponseFactoryInterface,
        ) -> LoaderlessAuthenticator:
            return LoaderlessAuthenticator(responses)

        loaderless_authenticator.__name__ = f"loaderless_authenticator_{firewall_name}"
        loaderless_authenticator.__qualname__ = loaderless_authenticator.__name__
        return (services.set(loaderless_authenticator, qualifier=firewall_name).key,)
