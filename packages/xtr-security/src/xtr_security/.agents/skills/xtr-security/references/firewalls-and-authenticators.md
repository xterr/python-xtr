# Firewalls, providers and authenticators

Every field an application writes, and the pieces it writes itself. Import the configurations
from `xtr_security.bundle`.

## `SecurityConfig`

| Field | Default | What it is |
| --- | --- | --- |
| `firewalls` | `{}` | The firewalls, keyed by name, matched in order — first match wins |
| `providers` | `{}` | The user providers, keyed by the name a firewall's `provider` refers to |
| `password_hashers` | `{}` | The hasher each user class, `"module:Class"` string or declared name is hashed by |
| `role_hierarchy` | `{}` | The roles each role reaches, expanding a token's roles |
| `access_control` | `()` | The access-control rules, tried in order |
| `access_decision_manager` | affirmative | `AccessDecisionManagerConfig` — how the votes become one decision |
| `expose_security_errors` | `ExposeSecurityLevel.NONE` | How much of an authentication failure reaches the client |
| `trace_votes` | `None` | Announce every vote as an event; `None` follows the kernel's debug flag |
| `authenticator_factories` | built-ins | The factories that build firewalls' authenticators |
| `token_handler_factories` | built-ins | The factories that build access-token handlers |
| `user_provider_factories` | built-ins | The factories that build user providers |

A firewall naming a `provider` that is not declared fails the build with
`InvalidConfigurationError`, as the configuration is written.

## `FirewallConfig`

| Field | Default | What it is |
| --- | --- | --- |
| `pattern` | `None` | A regular expression matched against the request path |
| `host` | `None` | A regular expression matched against the request host |
| `methods` | `()` | The HTTP methods claimed; every method when empty |
| `request_matcher` | `None` | A callable `(Request) -> bool`, tried last |
| `security` | `True` | `False` lets every request the firewall claims through untouched |
| `stateless` | `True` | Only `True` is accepted; `False` raises `InvalidConfigurationError` |
| `provider` | `None` | The name of the user provider the firewall loads users from |
| `user_checker` | `None` | A user-checker service type, or the default in-memory checker |
| `entry_point` | `None` | The authenticator whose challenge answers an unauthenticated request |
| `access_denied_handler` | `None` | A handler service type for a denied, fully-authenticated caller |
| `authenticators` | `()` | The authenticator configurations the firewall runs |
| `required_badges` | `()` | Badge types every passport must carry |

A secured firewall with no authenticators is refused. A firewall with no `pattern`, `host`,
`methods` or `request_matcher` claims every request, so register it last.

## `AccessControlConfig`

`AccessControlConfig(path, attribute, host=None, methods=(), ips=(), firewall=None)`. `path` and
`host` are regular expressions, searched against the request. One attribute per rule, by design:
a rule needing two conditions is two rules, or one closure attribute.

## User providers

| Configuration | Loads a user from |
| --- | --- |
| `InMemoryUserProviderConfig(users={identifier: {"password": …, "roles": (…), "enabled": True}})` | the table written inline |
| `ChainUserProviderConfig(providers=("db", "ldap"))` | each named provider in turn; needs at least one |
| `ServiceUserProviderConfig(service=MyUserProvider, qualifier=None)` | a provider the container provides |

Write your own by implementing `UserProviderInterface` from `xtr_security_core`:
`load_user_by_identifier(identifier)` (raising `UserNotFoundError`) and
`supports_class(user_class)`. Register it `@as_service` and name it with
`ServiceUserProviderConfig`. Implement `PasswordUpgraderInterface` as well and the password
migrating listener re-stores a rehashed password for you after a successful sign-in.

A configured provider is also injectable by name:

```python
from typing import Annotated

from xtr_dependency_injection import Target
from xtr_security_core import InMemoryUserProvider

users: Annotated[InMemoryUserProvider, Target("users")]
```

## Access-token authenticators

`AccessTokenConfig(token_handler, token_extractors=("header",), realm=None)`. Extractors are
`"header"`, `"query"` and `"body"`, tried in order; the first one's scheme documents the firewall
in the generated schema. `realm` is named in the `WWW-Authenticate` challenge.

| Token handler | Verifies |
| --- | --- |
| `ServiceTokenHandlerConfig(service=MyTokenHandler, qualifier=None)` | with a handler you registered as a service |
| `OidcTokenHandlerConfig(issuers=(…), audience="…", keyset=… \| discovery_uri=… \| jwks_uri=…)` | a third-party OIDC issuer's tokens; needs the `oidc` extra |

`OidcTokenHandlerConfig` takes **exactly one** key source, and at least one issuer and an
audience; `algorithms` default to `("RS256",)`, `claim` to `"sub"`, plus `leeway`,
`enforce_at_jwt_type` and `allow_insecure_http`. `exp` is required on a token: one that never
expires is refused.

## The token handler you write

A handler turns a token string into a `UserBadge` — the identifier, and how to load the user.
Raise `InvalidAccessTokenError` for anything it cannot trust; that becomes an `invalid_token`
challenge.

```python
from xtr_dependency_injection import as_service
from xtr_security_core import InMemoryUser
from xtr_security_http import AccessTokenHandlerInterface, InvalidAccessTokenError, UserBadge


@as_service
class MyTokenHandler(AccessTokenHandlerInterface):
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        if access_token != "s3cret":
            raise InvalidAccessTokenError("Unknown token.")
        return UserBadge("ada", user_loader=lambda i: InMemoryUser(i, roles=["ROLE_USER"]))
```

Leave the `user_loader` out and the firewall's own `provider` loads the user, so the token carries
identity and your store carries the roles — usually what you want.

## What runs on a request

1. The firewall map matches the request, or the named firewall is taken.
2. The first authenticator whose `supports()` is not `False` reads the request into a `Passport`
   of badges and credentials.
3. Listeners resolve the badges: the user provider gives a `UserBadge` its loader, credentials are
   verified, the account's pre- and post-authentication checks run.
4. Every badge must be resolved and every `required_badges` type present, or
   `BadCredentialsError`.
5. A token is created and stored; the access map's rule for the request is decided against it.

An unknown user in a password passport is still verified against a dummy hash, so a bad
identifier and a bad password take the same time.

`expose_security_errors` controls what a client learns: `ExposeSecurityLevel.NONE` reports
everything as bad credentials, `ACCOUNT_STATUS` reveals disabled, locked and expired accounts,
`ALL` reveals the failure. Leave it at `NONE` in production.

## Listening to a firewall's events

Each firewall dispatches `CheckPassportEvent`, `AuthenticationTokenCreatedEvent`,
`AuthenticationSuccessEvent`, `LoginSuccessEvent` and `LoginFailureEvent` on a dispatcher of its
own. A listener of them on the main dispatcher hears every firewall; to hear one alone, name its
dispatcher:

```python
from xtr_event_dispatcher import as_event_listener
from xtr_security.bundle import firewall_dispatcher_name


@as_event_listener(dispatcher=firewall_dispatcher_name("api"))
def count_api_login(event: LoginSuccessEvent) -> None: ...
```

In debug mode `debug:event-dispatcher --dispatcher security.event_dispatcher.api` lists that
firewall's listeners.

## Challenges

The exception listener answers for you: an `AuthenticationError` becomes the firewall's
entry-point challenge, or a bare `401` with `WWW-Authenticate: Bearer`; an `AccessDeniedError`
becomes `403`, or the entry-point challenge when the caller is not fully authenticated, or an
`insufficient_scope` challenge when a scope was the denied attribute.

## Adding a kind of authenticator

Only a library shipping its own bundle needs this. Implement `AuthenticatorFactoryInterface`
(a `key`, a `priority`, a `config_type` and `create_authenticator(...)`) and prepend it onto the
security configuration from the bundle's `prepend_extension` hook with `add_authenticator_factory`.
`add_token_handler_factory` and `add_user_provider_factory` are the same seam for the other two
registries. An application configures what those factories accept; it does not write factories.
