"""The security configuration the scoped-provider fixture is built from.

Every firewall loads its users through :class:`ScopedUserProvider`, a service
of the request, so each kind of firewall the bundle wires is built over one:

- ``api`` — stateless, a bearer token naming the user, loaded by the firewall;
- ``chained`` — stateless, HTTP basic over a chain whose second member is the
  scoped provider;
- ``loaderless`` — stateless, a login leaving the user's load and the rehash's
  store to the firewall, with the scoped user checker;
- ``guarded`` — stateful, a form login carrying a forgery token, behind login
  throttling that lets one failure through;
- ``main`` — stateful, a form login, a JSON login, a login link, a remembered
  login and a switch-user block, with a logout and the scoped user checker.

The ``persistent`` environment keeps the remembered logins in series instead,
over a token provider of the request too.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from xtr_dependency_injection import configure, when
from xtr_security_core import InMemoryUser

from tests.fixtures.scoped_provider_app.authenticator import LoaderlessLoginConfig
from tests.fixtures.scoped_provider_app.services import (
    STORED_HASH,
    NamingTokenHandler,
    ScopedUserChecker,
    ScopedUserProvider,
)
from xtr_security.bundle import (
    AccessTokenConfig,
    ChainUserProviderConfig,
    FormLoginConfig,
    HttpBasicConfig,
    InMemoryUserProviderConfig,
    JsonLoginConfig,
    LoginLinkConfig,
    LoginThrottlingConfig,
    LogoutConfig,
    NativeHasherConfig,
    Pbkdf2HasherConfig,
    RememberMeConfig,
    SecurityConfig,
    ServiceTokenHandlerConfig,
    ServiceUserProviderConfig,
    SwitchUserConfig,
)
from xtr_security.firewall_config import FirewallConfig

__all__ = ["PERSISTENT_ENV", "keeping_remembered_logins_in_series", "security"]

#: The environment keeping remembered logins in series.
PERSISTENT_ENV: Final = "persistent"


@configure
def security() -> SecurityConfig:
    """Return the fixture's security configuration."""
    return SecurityConfig(
        providers={
            "users": ServiceUserProviderConfig(ScopedUserProvider),
            "memory": InMemoryUserProviderConfig(
                users={"carol": {"password": STORED_HASH, "roles": ["ROLE_USER"], "enabled": True}}
            ),
            "chained": ChainUserProviderConfig(providers=("memory", "users")),
        },
        password_hashers={
            InMemoryUser: NativeHasherConfig(migrate_from=(Pbkdf2HasherConfig(),)),
        },
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="users",
                authenticators=(
                    AccessTokenConfig(token_handler=ServiceTokenHandlerConfig(NamingTokenHandler)),
                ),
            ),
            "chained": FirewallConfig(
                pattern=r"^/chained",
                provider="chained",
                authenticators=(HttpBasicConfig(realm="chained"),),
            ),
            "loaderless": FirewallConfig(
                pattern=r"^/loaderless",
                provider="users",
                user_checker=ScopedUserChecker,
                authenticators=(LoaderlessLoginConfig(),),
            ),
            "guarded": FirewallConfig(
                pattern=r"^/guarded",
                stateless=False,
                provider="users",
                login_throttling=LoginThrottlingConfig(
                    secret="counting-secret", global_limit=50, local_limit=1
                ),
                authenticators=(
                    FormLoginConfig(
                        login_path="/guarded/login",
                        check_path="/guarded/login_check",
                        enable_csrf=True,
                        post_only=False,
                    ),
                ),
            ),
            "main": FirewallConfig(
                pattern=r"^/",
                stateless=False,
                provider="users",
                user_checker=ScopedUserChecker,
                logout=LogoutConfig(),
                switch_user=SwitchUserConfig(),
                authenticators=(
                    FormLoginConfig(login_path="/login", post_only=False),
                    JsonLoginConfig(check_path="/json_login"),
                    LoginLinkConfig(check_path="/link", path="/login", secret="link-secret"),
                    RememberMeConfig(secret="remember-secret", always_remember_me=True),
                ),
            ),
        },
    )


@configure
@when(PERSISTENT_ENV)
def keeping_remembered_logins_in_series(config: SecurityConfig) -> SecurityConfig:
    """Keep the main firewall's remembered logins in series, over the fixture's token provider."""
    main = config.firewalls["main"]
    authenticators = tuple(
        replace(authenticator, handler="persistent", token_provider="fixture_remember_me_tokens")
        if isinstance(authenticator, RememberMeConfig)
        else authenticator
        for authenticator in main.authenticators
    )
    return replace(
        config,
        firewalls={**config.firewalls, "main": replace(main, authenticators=authenticators)},
    )
