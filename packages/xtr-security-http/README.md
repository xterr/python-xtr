<div align="center">

# xtr-security-http

**The HTTP edge of security: firewalls, authenticators, bearer access tokens and the request surface.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

FastAPI already parses an `Authorization` header, documents a security scheme in OpenAPI, and
fills a dependency on a route. What it does not do is turn a credential into a *user*, enforce a
*rule* against that user before the endpoint runs, and answer an unauthenticated or denied
request with the right challenge. That part — a **firewall** over a slice of the request space,
the **authenticators** it runs, and the response it gives when authentication or authorization
fails — is this package.

It builds on [xtr-security-core](../xtr-security-core)'s users, tokens and voters, and on
[xtr-http-kernel](../xtr-http-kernel)'s request lifecycle:

- 🔥 **Firewalls** — a `FirewallMap` matches a request to one firewall; the firewall runs its
  authenticators once per request and checks the request against an access map.
- 🎟️ **Authenticators and passports** — an authenticator reads a request into a `Passport` of
  badges and credentials; a fixed event order resolves and checks it, then mints a token.
- 🪙 **Bearer access tokens** — extractors pull a token from a header, query or form; a handler
  turns it into a user. An OIDC handler verifies a third-party issuer's tokens.
- 🛂 **The FastAPI surface stays FastAPI's** — `Firewall`, `IsGranted` and `CurrentUser` are
  dependencies and decorators; the generated OpenAPI schema names each firewall's scheme.
- 🧩 **RFC 6750 challenges** — a `401` with `WWW-Authenticate: Bearer`, an `invalid_token` or
  `insufficient_scope` challenge, written for you.

What FastAPI already does, it keeps doing: scheme parsing, argument resolution and the generated
schema stay the framework's. This package is the user, the rule and the challenge around them.

## Install

```sh
uv add xtr-security-http                 # firewalls, authenticators, access tokens
uv add "xtr-security-http[oidc]"         # + verifying a third-party OIDC issuer's tokens
```

Requires Python 3.11+. The web framework and the security core come with the package; the `oidc`
extra adds [joserfc](https://jose.authlib.org/) and [httpx](https://www.python-httpx.org/) for
verifying and discovering an issuer's keys.

## Quick start

The HTTP edge is built from plain objects, and the pieces that turn a credential into a token
run without a container. Below: an access-token authenticator over a bearer-header extractor and
a handler you write, an access map matched with a request matcher, and the OAuth2 scope helpers —
all standalone.

```python
from __future__ import annotations

import asyncio

from starlette.requests import Request
from xtr_event_dispatcher import EventDispatcher
from xtr_security_core import InMemoryUser, TokenStorage
from xtr_security_core.authorization.access_decision_manager import AccessDecisionManager
from xtr_security_http import (
    AccessListener,
    AccessMap,
    AccessTokenAuthenticator,
    AccessTokenHandlerInterface,
    AuthenticatorManager,
    HeaderAccessTokenExtractor,
    InvalidAccessTokenError,
    OAuth2ScopeVoter,
    UserBadge,
    oauth2_scope,
)
from xtr_security_http.authorization.oauth2_scope_voter import parse_oauth2_scope
from xtr_security_http.request_matcher import PathRequestMatcher


class MyTokenHandler(AccessTokenHandlerInterface):
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        if access_token != "s3cret":
            raise InvalidAccessTokenError("Unknown token.")
        return UserBadge("ada", user_loader=lambda i: InMemoryUser(i, roles=["ROLE_USER"]))


def make_request(path: str, headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request(
        {"type": "http", "method": "GET", "path": path, "headers": raw, "query_string": b""}
    )


async def main() -> None:
    storage = TokenStorage()
    manager = AuthenticatorManager(
        authenticators=[
            AccessTokenAuthenticator(
                handler=MyTokenHandler(),
                extractor=HeaderAccessTokenExtractor(),
            )
        ],
        token_storage=storage,
        event_dispatcher=EventDispatcher(),
        firewall_name="api",
    )

    await manager.authenticate_request(make_request("/api/me", {"Authorization": "Bearer s3cret"}))
    token = storage.get_token()
    print("authenticated:", token is not None and token.get_user_identifier())

    access_map = AccessMap()
    access_map.add(PathRequestMatcher(r"^/api"), "ROLE_USER")
    AccessListener(access_map, AccessDecisionManager())  # decides a token against the rules
    print("rule attribute:", access_map.get_attribute(make_request("/api/me", {})))

    attribute = oauth2_scope("books:read", "books:write")
    print("oauth2_scope:", attribute)
    print("parse_oauth2_scope:", parse_oauth2_scope(attribute))
    print("voter supports:", OAuth2ScopeVoter().supports_attribute(attribute))


asyncio.run(main())
```

```console
authenticated: ada
rule attribute: ROLE_USER
oauth2_scope: OAUTH2_SCOPE(books:read books:write)
parse_oauth2_scope: ('books:read', 'books:write')
voter supports: True
```

### The full HTTP path needs the bundle

Running an actual firewall *on a FastAPI route* is more than these primitives. The `Firewall`
dependency resolves the `FirewallMap`, the token storage and the decision manager from the
container, and the `ExceptionListener` turns a security error into a challenge on the
[xtr-http-kernel](../xtr-http-kernel) lifecycle. Wiring all of that by hand is exactly what the
[`xtr-security`](../xtr-security) bundle exists to do: an application lists `SecurityBundle`,
writes firewalls as configuration, and uses `Firewall`, `IsGranted` and `CurrentUser` on its
routes. See [xtr-security's Quick start](../xtr-security#quick-start) for the whole loop, and its
[Use in an application](../xtr-security#use-in-an-application) for what adding it takes.

## Concepts

### Firewalls and the map

A **`FirewallContextInterface`** is one firewall's runtime pieces: its `name`, its
`authenticator_manager`, its `access_listener`, its own event `dispatcher`, the FastAPI `scheme`
it shows in OpenAPI, whether it has `security` at all, and the optional `entry_point`,
`access_denied_handler` and `scope_denied_handler` that answer a failure. A **`FirewallMap`**
holds those contexts: `match(request)` returns the first whose matcher claims the request,
`get(name)` fetches one by name (raising `UnknownFirewallError`), `has(name)` and `names()`
report what is registered. `FirewallMapInterface` is the protocol the bundle wires a
container-backed map to.

**`Firewall`** is the FastAPI dependency an application puts on a route or router.
`Firewall()` runs whichever firewall matches the request; `Firewall("api")` runs that one by
name and shows its exact scheme in OpenAPI. `firewall.scoped("books:read")` returns a variant
requiring scopes, and `Firewall` used as a decorator attaches to every route of a router or to a
single endpoint. Authentication runs **once per request** however many firewall dependencies a
route carries, memoised by firewall name. `FirewallScheme` is the `SecurityBase` a firewall
contributes to the schema; `FirewallSchemeRegistry` and `active_firewall_schemes(registry)` let
the generated schema name each firewall's scheme while the application is built.

### Authenticators, passports, badges and credentials

An **`AuthenticatorInterface`** answers `supports(request)` — `True` to handle and stop others,
`False` to skip, `None` to handle lazily (let a later authenticator try if this one yields no
token) — reads the request into a `Passport` with `authenticate(request)`, and mints a token
with `create_token(passport, firewall_name)`. `AbstractAuthenticator` is the base that builds a
`PostAuthenticationToken` carrying the user and roles.

A **`Passport`** gathers a `UserBadge` and other `BadgeInterface` badges, keyed by class
(`add_badge`, `get_badge`, `has_badge`, `get_user`, attributes). A badge
`is_resolved()` reports whether it has been handled; `check_if_completely_resolved()` raises
`BadCredentialsError` if any badge is still open. The badges:

| Badge | Resolves when | Carries |
|---|---|---|
| `UserBadge(identifier, user_loader=None, ...)` | a loader is set | the identifier and how to load the user |
| `PasswordUpgradeBadge(plaintext, upgrader=None)` | always | a verified plaintext to rehash and store |
| `PreAuthenticatedUserBadge()` | always | nothing — the user is already trusted |

A **`CredentialsInterface`** is a badge to verify: `PasswordCredentials(password)` holds a
plaintext (`get_password()`, `mark_resolved()`), `CustomCredentials(checker, credentials)` runs
a callable `verify(user)`. A **`SelfValidatingPassport`** carries a `PreAuthenticatedUserBadge`,
for an authenticator — like the access-token one — that already trusts the credential.

### The authenticator manager and its event order

**`AuthenticatorManager(authenticators, token_storage, event_dispatcher, firewall_name, ...)`**
runs authentication for one firewall. `authenticate_request(request)` drives a fixed order over
the firewall's own dispatcher:

1. the first authenticator whose `supports()` is not `False` reads the request into a passport;
2. **`CheckPassportEvent`** — listeners resolve the badges (load the user, verify the password);
3. every badge must report resolved, and every `required_badges` type must be present, else
   `BadCredentialsError`;
4. a token is created, then **`AuthenticationTokenCreatedEvent`** lets a listener replace it;
5. **`AuthenticationSuccessEvent`** ([core](../xtr-security-core)) runs the post-authentication
   account check;
6. the token is stored, the authenticator's success handler runs, and **`LoginSuccessEvent`**
   lets a listener migrate a password or replace the response.

A lazy authenticator that raises a plain `BadCredentialsError` is read as *no credential
presented* — it did not apply, so the next authenticator is tried. Any other failure is masked to
the configured `ExposeSecurityLevel` (`NONE` hides everything as bad credentials,
`ACCOUNT_STATUS` reveals disabled/locked/expired, `ALL` reveals the failure), announced as
**`LoginFailureEvent`**, offered to the authenticator's failure handler, and re-raised for the
entry point to turn into a challenge. `AuthenticationSuccessHandlerInterface` and
`AuthenticationFailureHandlerInterface` are the two handler shapes a route may answer with.

### Listeners

The bundle registers these on each firewall's dispatcher; they are the badge-resolving half of
the event order:

| Listener | Resolves |
|---|---|
| `UserProviderListener` | gives a `UserBadge` its loader from the firewall's user provider, unless it has one |
| `CheckCredentialsListener` | verifies a password passport's `PasswordCredentials` and `CustomCredentials` |
| `UserCheckerListener` | runs the account's pre- and post-authentication checks |
| `PasswordMigratingListener` | rehashes a password flagged by a `PasswordUpgradeBadge`, best-effort |

**The dummy-hash timing guard.** When a password passport names an *unknown* user,
`CheckCredentialsListener` still verifies against a dummy hash, so the timing of a bad username
and a bad password is the same — neither reveals which was wrong. The dummy is hashed once per
listener instance and kept, so no request pays the cost twice.

### Access map and request matchers

An **`AccessMap`** is an ordered list of rules: `add(request_matcher, attribute)` appends one,
`get_attribute(request)` returns the attribute the first matching rule requires. An
**`AccessListener(access_map, access_decision_manager)`** decides a token against that attribute
with `check_access(request, token)`, raising `AccessDeniedError` when it is not granted. A
**`RequestMatcherInterface`** answers `matches(request)`:

| Matcher | Claims a request by |
|---|---|
| `PathRequestMatcher(pattern)` | its path (searched, not anchored) |
| `HostRequestMatcher(pattern)` | its host |
| `MethodRequestMatcher(methods)` | its method |
| `IpRequestMatcher(ips)` | its client address |
| `ChainRequestMatcher(matchers)` | all of several matchers (an empty chain claims everything) |
| `CallableRequestMatcher(decide)` | a callable `(request) -> bool` |

### The exception listener: 401, 403 and RFC 6750

**`ExceptionListener`** is a subscriber on the [xtr-http-kernel](../xtr-http-kernel) exception
event. It turns a security error raised while handling into the right response:

- an **`AuthenticationError`** becomes the firewall's entry-point challenge, or a bare `401`
  with `WWW-Authenticate: Bearer` when the firewall has no entry point;
- an **`AccessDeniedError`** from a caller who is not fully authenticated becomes the entry-point
  challenge for insufficient authentication; from a fully authenticated caller, a scope challenge
  (when the denied attribute is a scope), the firewall's access-denied handler, or a plain `403`;
- a response an authentication handler produced is carried straight out.

`AccessTokenAuthenticator` is itself an `AuthenticationEntryPointInterface`: `start(request,
error)` answers a request with an RFC 6750 bearer challenge, naming `invalid_token` when a
present token was rejected, and the `realm` when one is configured.

### Decorators

Four markers put the edge on a route, and stay out of the generated schema:

| Decorator | Does |
|---|---|
| `Firewall(name=None, *, scopes=())` | run a firewall (matched or named) before the endpoint |
| `IsGranted(attribute, subject=None, *, message=None, status_code=None)` | require an attribute, raising `AccessDeniedError` (or answering `status_code`) |
| `CurrentUser(user_class=None, *, optional=False)` | inject the current user; `optional` yields `None` when anonymous |
| `IsGrantedContext` | the context a closure `IsGranted` attribute is handed (from [core](../xtr-security-core)) |

`IsGranted`'s `subject` is `None`, the name of a path parameter, or a callable used as a
dependency; its `attribute` is a string a voter matches or a callable
`(IsGrantedContext, subject) -> bool`. `CurrentUser` raises
`AuthenticationCredentialsNotFoundError` on an anonymous request (a `401`), or
`UnsupportedUserError` when the user is not the asked-for class.

### Access tokens

An **`AccessTokenExtractorInterface`** pulls a bearer token out of a request and names the
FastAPI `scheme()` it documents by; an **`AccessTokenHandlerInterface`** turns a token string
into a `UserBadge` with `get_user_badge_from(token)`, raising `InvalidAccessTokenError` when it
cannot be trusted. The extractors:

| Extractor | Reads a token from |
|---|---|
| `HeaderAccessTokenExtractor(header_name="Authorization", token_type="Bearer")` | a header, after a scheme prefix |
| `QueryAccessTokenExtractor(parameter_name="access_token")` | a query parameter |
| `FormEncodedBodyExtractor(field_name="access_token")` | a form field |
| `ChainAccessTokenExtractor(extractors)` | the first that finds one |

**`AccessTokenAuthenticator(handler, extractor, user_provider=None, ..., realm=None)`** reads the
token, validates it through the handler, and builds a `SelfValidatingPassport`; it copies the
badge's granted `scope` onto the token as `oauth2_scope`.

### OIDC

With the `oidc` extra, **`OidcTokenHandler`** verifies a third-party OpenID issuer's tokens:

```python
from xtr_security_http.access_token.oidc.oidc_token_handler import OidcTokenHandler
from xtr_security_http.oidc.oidc_discovery import DiscoveryOidcKeySetProvider
```

Its keys come from an `OidcKeySetProviderInterface` — `StaticOidcKeySetProvider(jwks)` for a
fixed JWKS, or `DiscoveryOidcKeySetProvider(base_uri=... | jwks_uri=..., ...)` which reads an
issuer's OpenID discovery document to find the `jwks_uri`, fetches the key set, caches it for a
`ttl`, and refreshes on a `kid` it does not know — no more than once every `refresh_cooldown`,
with a lock so concurrent callers share the one fetch. The handler checks the signature against
an explicit **algorithm allow-list** (refusing `none` and symmetric `HS*`), the `iss` against
the trusted issuers, the `aud` against the audience, and the time claims against a clock with
leeway. **`exp` is required** — a token that never expires is refused. A key set that cannot be
fetched, discovered or read raises `OidcKeySetError`; every discovery and JWKS endpoint must be
`https` unless insecure HTTP is explicitly allowed.

### OAuth2 scopes

A scope requirement is written as an access-control attribute. `oauth2_scope("books:read",
"books:write")` builds the string `"OAUTH2_SCOPE(books:read books:write)"`;
`parse_oauth2_scope(attribute)` reads the scopes back out, or `None` for anything not shaped like
it. **`OAuth2ScopeVoter`** grants when the token holds every asked-for scope, reading the
`oauth2_scope` attribute an authenticator copied onto it; **`InsufficientScopeAccessDeniedHandler(realm=None)`**
answers a denied scope with a `403` carrying the RFC 6750 `insufficient_scope` challenge.

### Security events

The event name constants a dispatcher keys on live in `security_events.py`: `CHECK_PASSPORT`,
`AUTHENTICATION_TOKEN_CREATED`, `LOGIN_SUCCESS`, `LOGIN_FAILURE`. A listener names the constant
rather than importing the event class, so a listener chosen at runtime stays in step.

## Errors

Everything this library raises derives from `SecurityError` (from
[xtr-security-core](../xtr-security-core)); authentication failures additionally derive from its
`AuthenticationError`, so one `except AuthenticationError` catches the token failures.

| Error | Base (besides `SecurityError`) | Raised when |
|---|---|---|
| `InvalidAccessTokenError` | `AuthenticationError` | a bearer token was present but could not be trusted — answered with an `invalid_token` challenge |
| `UnknownFirewallError` | `LookupError` | a firewall was asked for by a name none is registered under; carries `name` and `configured` |
| `FirewallNotBootedError` | `RuntimeError` | a firewall's OpenAPI scheme was read before the kernel booted or outside a request |

## Layout

```
xtr_security_http/
├── firewall_map.py             FirewallMap, matched or fetched by name
├── firewall_context_interface.py  one firewall's runtime pieces
├── firewall_scheme.py          the SecurityBase a firewall shows in OpenAPI
├── firewall/                   Firewall, AccessListener, ExceptionListener
├── authentication/             AuthenticatorManager, handlers, ExposeSecurityLevel
├── authenticator/              AuthenticatorInterface, AccessTokenAuthenticator, passport/, token/
├── access_token/               extractors, handler interface, oidc/ (OidcTokenHandler)
├── oidc/                       DiscoveryOidcKeySetProvider
├── access_map.py               the ordered access-control rules
├── request_matcher/            path, host, method, ip, chain, callable
├── authorization/              OAuth2ScopeVoter, oauth2_scope, the scope-denied handler
├── decorator/                  Firewall, IsGranted, CurrentUser, IsGrantedContext
├── entry_point/                AuthenticationEntryPointInterface
├── event/                      the four firewall events
├── security_events.py          the name each is dispatched under
├── event_listener/             the listeners the bundle registers (incl. the timing guard)
└── exception/                  the errors this package adds
```

## In an application

This package works on its own and ships no bundle. The
[`xtr-security`](../xtr-security#use-in-an-application) bundle wires it — the firewalls, the
authenticators, the access map, the exception listener, the `Firewall`/`IsGranted`/`CurrentUser`
surface — into an application on [xtr-dependency-injection](../xtr-dependency-injection), with
firewalls written as configuration. See that package's
[Use in an application](../xtr-security#use-in-an-application).

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-security-http`; run the commands below from there. The `python-xtr-security-http`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
