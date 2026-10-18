<div align="center">

# xtr-security

**The security bundle for xtr applications: the family facade and the container wiring that configures it.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

The security family is three libraries — [xtr-security-core](../xtr-security-core),
[xtr-security-http](../xtr-security-http) and [xtr-password-hasher](../xtr-password-hasher) —
each usable on its own. Wiring them together
by hand is a lot of moving parts: a token storage per request, voters gathered into a decision
manager, a user provider and a password hasher, and, per firewall, an authenticator over its own
event dispatcher, an access map, an entry point and the OpenAPI scheme it shows.

This package is the one bundle of the family. An application lists `SecurityBundle`, writes one
`SecurityConfig`, and the container owns the rest.

- 🔥 **Firewalls as configuration** — a slice of the request space, how it authenticates, and
  the rules it enforces, in one frozen value.
- 🧩 **Open at the seams** — a third-party bundle adds a kind of authenticator, token handler or
  user provider through the factory registries, without this package knowing it.
- 🪪 **The FastAPI surface stays FastAPI's** — `IsGranted` and `CurrentUser` are dependencies
  and decorators; the firewall itself runs as a subscriber over the kernel lifecycle's events,
  before routing, and a route documents its security with the framework's own params.
- 🔒 **Scoped to the request** — the token storage, the authorization checker and the `Security`
  facade are per-request; concurrent requests never share them.

## Install

```sh
uv add xtr-security                    # the bundle, wiring core, http and the password hasher
uv add xtr-console                     # beside it: debug:firewall and security:hash-password
uv add "xtr-security-http[oidc]"       # + verifying third-party OIDC issuers' tokens
```

Requires Python 3.11+. The core, http-edge and password-hasher libraries come with the package;
[xtr-console](../xtr-console), installed beside it, adds the commands. The `oidc` extra of
[xtr-security-http](../xtr-security-http) adds joserfc and httpx and the OIDC token handler; the
bundle registers its factory only when that extra is installed. Self-issued JSON Web Tokens are a
separate package, [xtr-security-jwt](../xtr-security-jwt), which depends on this one and
registers itself through the [extension points](#extending).

## Quick start

Write a token handler that turns a bearer token into a user, configure a firewall that uses it,
and secure the routes — no JSON Web Tokens needed.

```python
# app/security_handler.py
from xtr_dependency_injection import as_service
from xtr_security_core import InMemoryUser
from xtr_security_http import UserBadge
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)
from xtr_security_http.exception import InvalidAccessTokenError


@as_service
class MyTokenHandler(AccessTokenHandlerInterface):
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        if access_token != "s3cret":
            raise InvalidAccessTokenError("Unknown token.")
        return UserBadge("alice", user_loader=lambda i: InMemoryUser(i, roles=["ROLE_USER"]))
```

```python
# app/config/security.py
from xtr_dependency_injection import configure
from xtr_security.bundle import (
    AccessControlConfig,
    AccessTokenConfig,
    FirewallConfig,
    SecurityConfig,
    ServiceTokenHandlerConfig,
)

from app.security_handler import MyTokenHandler


@configure
def security() -> SecurityConfig:
    return SecurityConfig(
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                authenticators=(
                    AccessTokenConfig(
                        token_handler=ServiceTokenHandlerConfig(MyTokenHandler),
                        realm="api",
                    ),
                ),
            ),
        },
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
```

```python
# app/web.py
from typing import Annotated

from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser, IsGranted

from app.bundles import BUNDLES

app = FastAPI()


@app.get("/api/me")
async def me(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, str]:
    return {"user": user.get_user_identifier()}


@app.get("/api/books")
async def books() -> list[str]: ...


@app.delete("/api/books/{isbn}")
@IsGranted("ROLE_ADMIN")
async def delete_book(isbn: str) -> None: ...


kernel = Kernel("app", concurrent_scoped_access=True)
setup(app, kernel)
```

```console
$ curl -i localhost:8000/api/me
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="api"

$ curl -i -H 'Authorization: Bearer s3cret' localhost:8000/api/me
HTTP/1.1 200 OK

{"user":"alice"}
```

## Configure

`SecurityConfig` is a frozen dataclass buildable with no arguments; every field has a default,
so the zero-config path is no firewalls and the affirmative decision strategy.

| Field | Default | What it is |
|---|---|---|
| `firewalls` | `{}` | The firewalls, keyed by name, matched in order — first match wins |
| `providers` | `{}` | The user providers, keyed by the name firewalls refer to |
| `password_hashers` | `{}` | The hasher each user class, `"module:Class"` string or name is hashed by |
| `role_hierarchy` | `{}` | The roles each role reaches, expanding a token's roles |
| `access_control` | `()` | The access-control rules, tried in order |
| `access_decision_manager` | affirmative | How the voters' answers become one decision |
| `expose_security_errors` | `NONE` | How much of an authentication failure reaches the client |
| `trace_votes` | `None` | Announce every vote as an event and log every decision; `None` follows `kernel.debug` |
| `authenticator_factories` | built-ins | The factories that build firewalls' authenticators |
| `token_handler_factories` | built-ins | The factories that build access-token handlers |
| `user_provider_factories` | built-ins | The factories that build user providers |

### Firewalls

`FirewallConfig` claims a slice of the request space and says how it authenticates:

| Field | Default | What it is |
|---|---|---|
| `pattern` | `None` | A regular expression matched against the request path |
| `host` | `None` | A regular expression matched against the request host |
| `methods` | `()` | The HTTP methods claimed; every method when empty |
| `request_matcher` | `None` | A callable `(ServerRequestInterface) -> bool`, tried last |
| `security` | `True` | `False` lets every request the firewall claims through untouched |
| `stateless` | `True` | Only `True` is accepted in this version |
| `provider` | `None` | The user provider the firewall loads users from; with none here and none configured at all, an authenticator that needs one gets a `MissingUserProvider` that fails, naming the firewall, when first used |
| `user_checker` | `None` | A user-checker service type, or the default in-memory checker |
| `entry_point` | `None` | The authenticator whose challenge answers an unauthenticated request |
| `access_denied_handler` | `None` | A handler for a denied, fully-authenticated caller |
| `authenticators` | `()` | The authenticator configurations the firewall runs |
| `required_badges` | `()` | Badge types every passport must carry |

The matchers those fields build come from [xtr-http-foundation](../xtr-http-foundation), and each
of them — `request_matcher`'s callable included — reads the request as a message.
`pattern` matches the path below the application's mount, with per-cent escapes undone; `host` is
matched without regard to case.

The firewalls run as the firewall — a subscriber `SecurityBundle` registers over the kernel
lifecycle's events, before routing — so the routes carry no firewall dependency of their own:
each request runs the first firewall whose matcher claims it, authenticated once, and a route
documents its security with the framework's own params.

### Firewall listeners

A firewall's listener chain — steps implementing the HTTP edge's
`FirewallListenerInterface`, each declaring its `get_priority()` — is put in running order by the
bundle's `SortFirewallListenersPass`: higher priority first, the gathering order for listeners
that share one, and a listener's `@FirewallListenerOrder(before=..., after=...)` declaration
settling how it stands against its neighbours within a shared priority — a constraint that
would cross a priority fails the build, naming the firewall.

Every secured firewall's chain carries its own authentication step — the
`AuthenticatorManagerListener` running that firewall's authenticator manager — registered by
the bundle under `firewall_manager_listener_name(firewall)` and parked ahead of the listeners
the `listeners` configuration names, so no application names it itself; a
`@FirewallListenerOrder` constraint addresses it by that qualifier to stand against it. When
the event dispatcher bundle traces, `MakeFirewallsManagerListenerTraceablePass` swaps the step
for the traceable variant, so a traced firewall's chain explains its authentication.

The chain carries the firewall's access step the same way: an `AccessListener` over the
request's token storage, the decision manager and the firewall's own access map, registered
under `firewall_access_listener_name(firewall)` and ordered by its `-255` priority after the
authentication step.

### Token handlers

An access-token authenticator (`AccessTokenConfig`) names a `token_handler` the bundle builds
through a factory matched by its type:

| Configuration | Key | Verifies |
|---|---|---|
| `ServiceTokenHandlerConfig(service)` | `id` | A handler the application registered as a service |
| `OidcTokenHandlerConfig(issuers, audience, …)` | `oidc` | A third-party OIDC issuer's tokens (needs the `oidc` extra) |

`OidcTokenHandlerConfig` takes exactly one key source — `keyset` (a JWKS document), `discovery_uri`
(an issuer base URI the `jwks_uri` is discovered from) or `jwks_uri` — plus the `issuers` and
`audience` a valid token must carry; `algorithms` default to `("RS256",)`, `claim` to `"sub"`.

### Access control

`AccessControlConfig` is a request pattern and the one attribute a matching request must hold —
a role, `"IS_AUTHENTICATED"`, `"PUBLIC_ACCESS"`, or an `OAUTH2_SCOPE(...)` string. Rules are
tried in order, so a narrow `^/api/admin` rule comes before the broad `^/api`.
`path` matches below the application's mount with per-cent escapes undone, `host` without regard
to case; an `ips` entry is an address or a network, written in CIDR or netmask form.

### Voters

The decision manager gathers every voter: the built-in role-hierarchy, authenticated, OAuth2
scope and closure voters, and every application voter — a class implementing
`VoterInterface`, autoconfigured with the `security.voter` tag. When `trace_votes` is on, each is
wrapped so its answer is announced as a `VoteEvent`, and `AccessDecisionManagerInterface` is a
`TraceableAccessDecisionManager` built per request: it logs every decision, with the votes the
bundle's `VoteEvent` listener feeds it, readable from `get_decision_log()` until the request
ends.

## Extending

A third-party bundle adds a kind of authenticator, token handler or user provider by prepending
its factory onto the security config from its `prepend_extension` hook — the seam an OAuth2
server plugs into:

```python
from xtr_dependency_injection import Bundle, as_bundle, required_bundle
from xtr_security.bundle import add_authenticator_factory, add_token_handler_factory
from xtr_security.bundle import SecurityBundle


@required_bundle(SecurityBundle)
@as_bundle("oauth2")
class OAuth2Bundle(Bundle):
    def prepend_extension(self, builder) -> None:
        builder.prepend_extension_config("security", add_authenticator_factory(OAuth2Factory()))
        builder.prepend_extension_config(
            "security", add_token_handler_factory(IntrospectionFactory())
        )
```

An `AuthenticatorFactoryInterface` carries a `key`, a `priority`, a `config_type` and
`create_authenticator(...)`; a firewall lists an instance of the factory's `config_type` under
its `authenticators`, and the bundle matches it to the factory. `TokenHandlerFactoryInterface`
and `UserProviderFactoryInterface` are the same shape for the other two registries.
A factory whose authenticator can settle on a user without a provider — as the access-token one
can, its handler building the user — inherits `StatelessAuthenticatorFactoryInterface`, and is
handed no provider rather than a `MissingUserProvider` when the application configures none.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add xtr-security`; install [xtr-console](../xtr-console) beside it for
  `debug:firewall` and `security:hash-password`.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below: it lists
  `SecurityBundle`, which brings the event dispatcher and http-kernel bundles with it. There is no
  config file, environment or ignore line to write; it prints the `concurrent_scoped_access=True`,
  `setup(app, kernel)` and `config/security.py` steps, which a recipe cannot make for you.
- **Activate** — `SecurityBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
  from `xtr_security.bundle`. Then call `setup(app, kernel)` where the application is built, and
  build the kernel with `concurrent_scoped_access=True` so concurrent requests keep their own
  token storage.
- **Brings along** — the [event dispatcher](../xtr-event-dispatcher) and
  [http-kernel](../xtr-http-kernel) bundles always, because the firewalls dispatch through the
  one and answer on the other's exception event; the [clock](../xtr-clock) bundle, installed
  with the security core, whose clock the trust resolver measures recent authentication with;
  the [logging](../xtr-logging) and [console](../xtr-console) bundles whenever those packages
  are installed.
- **Configure** — the zero-config path gives no firewalls and the affirmative strategy. A
  `<app>/config/security.py` `@configure` function returning a `SecurityConfig` changes that —
  see [Configure](#configure) and [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing; an application reads its own secrets through `env(...)` in its
  configuration.
- **Ignore** — nothing.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/security.py`, then
  `uv remove xtr-security`.
- **Check** — `debug:bundles` shows `security` as `listed` and `active`, `event_dispatcher`,
  `http_kernel` and `clock` as `required`; `debug:firewall` lists the configured firewalls.

## Kernel / bundle

```python
# app/bundles.py
from xtr_security.bundle import SecurityBundle

BUNDLES = {SecurityBundle: {"all": True}}
```

`SecurityBundle` registers the token storage (scoped), the trust resolver over the clock bundle's
clock, the role hierarchy, the voters and the decision manager (traceable per request when
`trace_votes` is on), the authorization checker — also under `UserAuthorizationCheckerInterface`
and `GuestAuthorizationCheckerInterface` — and the `Security` facade (both scoped), the password
hasher factory and the user hasher, the user providers, and — per
firewall — its own event dispatcher with the login listeners, its authenticators, its access
map and its entry point, gathered into a `FirewallMap`. The bundle also registers the
firewall itself — a subscriber over the kernel lifecycle's events, one listener per event,
resolving the map per call from the request's scope — so every request the configuration's
firewalls claim is authenticated before routing. A firewall's
`listeners` configuration names the qualifiers of its listener chain; the bundle parks them on
the firewall's context definition, where `SortFirewallListenersPass` orders them, and the
context carries the ordered chain — with the global exception listener and, while the firewall
configures none, no logout listener — so `await firewall_map.get_listeners(message)` answers
the matched firewall's `(chain, exception_listener, logout_listener)`. The exception
listener turns a security error into a response on the http-kernel lifecycle. Its zero-config
path builds and boots with no configuration and touches no I/O until a request arrives.

Each firewall dispatches its security events — `CheckPassportEvent`,
`AuthenticationTokenCreatedEvent`, `AuthenticationSuccessEvent`, `LoginSuccessEvent`,
`LoginFailureEvent` — on a dispatcher of its own, named by `firewall_dispatcher_name(firewall)`.
A listener of those events on the main dispatcher hears every firewall
(`RegisterGlobalSecurityEventListenersPass` copies it onto each); one naming a firewall's
dispatcher hears that firewall alone:

```python
from xtr_event_dispatcher import as_event_listener
from xtr_security.bundle import firewall_dispatcher_name


@as_event_listener()  # every firewall
def audit_login(event: LoginSuccessEvent) -> None: ...


@as_event_listener(dispatcher=firewall_dispatcher_name("api"))  # the api firewall alone
def count_api_login(event: LoginSuccessEvent) -> None: ...
```

In debug mode `MakeFirewallsEventDispatcherTraceablePass` traces every firewall's dispatcher,
as the event dispatcher bundle traces its own; `debug:event-dispatcher --dispatcher
security.event_dispatcher.api` lists one firewall's listeners.

With a console bundle active it also registers `debug:firewall [name]`, which lists the
configured firewalls or describes one, and `security:hash-password`, which hashes a password
with the configured factory.

## Errors

Everything the family raises derives from `SecurityError` (from
[xtr-security-core](../xtr-security-core)); this package adds one.

| Error | Raised when |
|---|---|
| `InvalidConfigurationError` | A security configuration the bundle cannot turn into services — an unknown provider, a firewall that is not stateless, an authenticator with no factory, an ambiguous entry point; also a `ValueError` |

## Layout

```
xtr_security/
├── security.py                the Security facade
├── firewall_config.py         FirewallConfig, the firewall an application writes
├── exception/                 InvalidConfigurationError
├── command/                   debug:firewall
├── factory/                   authenticator factory interface + AccessTokenFactory,
│                              with add_authenticator_factory
├── access_token/              token-handler factory interface + built-ins,
│                              with add_token_handler_factory
├── user_provider/             user-provider factory interface + built-ins,
│                              with add_user_provider_factory
└── bundle/
    ├── security_bundle.py     SecurityBundle
    ├── security_config.py      SecurityConfig
    ├── firewall_context.py    FirewallContext, one firewall's runtime pieces (internal)
    ├── firewall_manager_listener_name.py  the qualifier of a firewall's manager listener
    ├── make_firewalls_manager_listener_traceable_pass.py  traces the manager listeners
    ├── sort_firewall_listeners_pass.py  orders each firewall's listener chain
    └── *_configs.py           the configs an application writes, incl. password_hasher_configs
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-security`; run the commands below from there. The `python-xtr-security` repository
is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync --all-packages --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest --cov
```

## License

MIT — see [LICENSE](LICENSE).
