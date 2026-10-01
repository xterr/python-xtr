"""A configuration exercising the in-memory and chain providers, extractors, hashers.

An in-memory provider with inline users, a chain over it, an access-token
authenticator reading the token from the header, the query and the body, native
password hashers and vote tracing turned on — so a container test reaches the
provider, extractor, hasher and tracing wiring the served fixtures leave aside.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_security_core import InMemoryUser

from tests.fixtures.wiring_app.services import WiringTokenHandler
from xtr_security.bundle import (
    AccessControlConfig,
    AccessTokenConfig,
    ChainUserProviderConfig,
    FirewallConfig,
    InMemoryUserProviderConfig,
    NativeHasherConfig,
    SecurityConfig,
    ServiceTokenHandlerConfig,
)

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return a configuration reaching the provider, extractor and hasher wiring."""
    return SecurityConfig(
        providers={
            "in_memory": InMemoryUserProviderConfig(
                users={"alice": {"password": "hashed", "roles": ["ROLE_USER"], "enabled": True}}
            ),
            "chain": ChainUserProviderConfig(providers=("in_memory",)),
        },
        password_hashers={InMemoryUser: NativeHasherConfig()},
        trace_votes=True,
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="chain",
                authenticators=(
                    AccessTokenConfig(
                        token_handler=ServiceTokenHandlerConfig(WiringTokenHandler),
                        token_extractors=("header", "query", "body"),
                        realm="api",
                    ),
                ),
            )
        },
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
