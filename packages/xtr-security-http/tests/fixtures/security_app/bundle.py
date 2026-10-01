"""A container fixture wiring one firewall, its token storage and its decisions.

Registers a single :class:`FirewallMap` with an ``api`` firewall, a shared
token storage, an access-decision manager and a trust resolver, so an
integration test can drive :func:`run_firewall`, the exception listener and the
route markers against a real container.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from fastapi.security import HTTPBearer
from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle
from xtr_security_core.authentication.authentication_trust_resolver import (
    AuthenticationTrustResolver,
)
from xtr_security_core.authentication.authentication_trust_resolver_interface import (
    AuthenticationTrustResolverInterface,
)
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.storage.token_storage_interface import (
    TokenStorageInterface,
)
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.authorization import AccessDecisionManager, RoleVoter
from xtr_security_core.authorization.access_decision_manager_interface import (
    AccessDecisionManagerInterface,
)
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.contexts import FakeFirewallContext
from tests.support.dispatchers import RecordingDispatcher
from xtr_security_http.access_map import AccessMap
from xtr_security_http.authorization.oauth2_scope_voter import OAuth2ScopeVoter
from xtr_security_http.exception import InvalidAccessTokenError
from xtr_security_http.firewall.access_listener import AccessListener
from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.request_matcher.path_request_matcher import PathRequestMatcher

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator
    from xtr_security_core.exception import AccessDeniedError, AuthenticationError

__all__ = ["SecurityFixtureBundle"]


@final
class _FakeManager:
    """Authenticates the fixture's known bearer tokens into a shared storage."""

    def __init__(self, storage: TokenStorage) -> None:
        self._storage = storage

    def supports(self, request: Request) -> bool | None:
        del request
        return None

    async def authenticate_request(self, request: Request) -> Response | None:
        auth = request.headers.get("authorization", "")
        if auth == "Bearer good":
            token = UsernamePasswordToken(
                InMemoryUser("alice", roles=["ROLE_USER"]),
                "api",
                ["ROLE_USER"],
            )
            token.set_attribute("oauth2_scope", ["books:read"])
            self._storage.set_token(token)
        elif auth == "Bearer admin":
            self._storage.set_token(
                UsernamePasswordToken(
                    InMemoryUser("root", roles=["ROLE_USER", "ROLE_ADMIN"]),
                    "api",
                    ["ROLE_USER", "ROLE_ADMIN"],
                ),
            )
        elif auth == "Bearer bad":
            raise InvalidAccessTokenError("The token is not known.")
        return None


@final
class _FakeEntryPoint:
    """Answers an unauthenticated request with a bare bearer challenge."""

    async def start(self, request: Request, error: AuthenticationError | None = None) -> Response:
        from starlette.responses import JSONResponse  # noqa: PLC0415

        del request, error
        return JSONResponse(
            {"error": "unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="api"'},
        )


@final
class _FakeAccessDeniedHandler:
    """Answers a denied, fully-authenticated caller with a 403."""

    async def handle(self, request: Request, error: AccessDeniedError) -> Response | None:
        from starlette.responses import JSONResponse  # noqa: PLC0415

        del request, error
        return JSONResponse({"error": "forbidden"}, status_code=403)


@final
class _FakeScopeDeniedHandler:
    """Answers a denied scope with an insufficient-scope challenge."""

    async def handle(self, request: Request, error: AccessDeniedError) -> Response | None:
        from starlette.responses import JSONResponse  # noqa: PLC0415

        del request, error
        return JSONResponse(
            {"error": "insufficient_scope"},
            status_code=403,
            headers={"WWW-Authenticate": 'Bearer error="insufficient_scope"'},
        )


def _firewall_map(storage: TokenStorage, manager: AccessDecisionManager) -> FirewallMap:
    access_map = AccessMap()
    access_map.add(PathRequestMatcher(r"^/api"), "ROLE_USER")
    context = FakeFirewallContext(
        name="api",
        authenticator_manager=_FakeManager(storage),
        access_listener=AccessListener(access_map, manager),
        dispatcher=RecordingDispatcher(),
        scheme=HTTPBearer(auto_error=False),
        entry_point=_FakeEntryPoint(),
        access_denied_handler=_FakeAccessDeniedHandler(),
        scope_denied_handler=_FakeScopeDeniedHandler(),
    )
    return FirewallMap(((PathRequestMatcher(r"^/api"), context),))


@final
@as_bundle("security_fixture")
class SecurityFixtureBundle(Bundle):
    """Registers one firewall, its storage, its decisions and a trust resolver."""

    @override
    def load_extension(
        self,
        config: object,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        del config, builder
        storage = TokenStorage()
        manager = AccessDecisionManager([RoleVoter(), OAuth2ScopeVoter()])
        resolver = AuthenticationTrustResolver()

        _ = services.instance(storage)
        _ = services.alias(TokenStorageInterface, TokenStorage)
        _ = services.instance(manager)
        _ = services.alias(AccessDecisionManagerInterface, AccessDecisionManager)
        _ = services.instance(resolver)
        _ = services.alias(AuthenticationTrustResolverInterface, AuthenticationTrustResolver)
        _ = services.instance(_firewall_map(storage, manager))
