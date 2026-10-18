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
- 🛂 **The FastAPI surface stays FastAPI's** — `IsGranted` and `CurrentUser` are dependencies
  and decorators; the firewall runs as a subscriber over the request lifecycle, before
  routing, and a route documents its security with the framework's own params.
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

from xtr_event_dispatcher import EventDispatcher
from xtr_http_foundation import PathRequestMatcher
from xtr_http_message import ServerRequest
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
from xtr_security_http._security_state import SecurityState
from xtr_security_http.authorization.oauth2_scope_voter import parse_oauth2_scope


class MyTokenHandler(AccessTokenHandlerInterface):
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        if access_token != "s3cret":
            raise InvalidAccessTokenError("Unknown token.")
        return UserBadge("ada", user_loader=lambda i: InMemoryUser(i, roles=["ROLE_USER"]))


def make_message(path: str, headers: dict[str, str] | None = None) -> ServerRequest:
    return ServerRequest("GET", f"https://example.com{path}", dict(headers or {}))


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

    message = make_message("/api/me", {"Authorization": "Bearer s3cret"})
    state = SecurityState()
    manager.supports(message, state)
    await manager.authenticate_request(message, state)
    token = storage.get_token()
    print("authenticated:", token is not None and token.get_user_identifier())

    access_map = AccessMap()
    access_map.add(PathRequestMatcher(r"^/api"), "ROLE_USER")
    AccessListener(
        storage, AccessDecisionManager(), access_map
    )  # decides a token against the rules
    print("rule attribute:", (await access_map.get_patterns(make_message("/api/me")))[0])

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

Running an actual firewall over a served request is more than these primitives. The `Firewall`
subscriber runs the chain of the firewall a request matched over the
[xtr-http-kernel](../xtr-http-kernel) lifecycle — before routing — and the `ExceptionListener`
turns a security error into a challenge. Wiring all of that is exactly what the
[`xtr-security`](../xtr-security) bundle exists to do: an application lists `SecurityBundle`
and writes firewalls as configuration. See [xtr-security's Quick
start](../xtr-security#quick-start) for the whole loop, and its
[Use in an application](../xtr-security#use-in-an-application) for what adding it takes.

## Concepts

### Firewalls and the map

A **`FirewallContextInterface`** is one firewall's runtime pieces: its `name`, its
`authenticator_manager`, its `access_listener`, whether it has `security` at all, the optional
`entry_point`,
`access_denied_handler` and `scope_denied_handler` that answer a failure, and its
listener chain — `listeners` in the order they run (the order the bundle's sorting
pass left them in), the `exception_listener` that answers a security error, and the
optional `logout_listener`. A **`FirewallMap`** holds those contexts: `await match(message)`
returns the first whose matcher claims the request message, `get(name)` fetches one by
name (raising `UnknownFirewallError`), `has(name)` and `names()` report what is
registered, and `await get_listeners(message)` answers the matched firewall's
`(listeners, exception_listener, logout_listener)` — or an empty chain and no
listeners when no firewall claims the message. `FirewallMapInterface` is the protocol
the bundle wires a container-backed map to.

**`Firewall`** is the subscriber that runs the firewalls: a listener over the kernel
lifecycle's events that the [xtr-security](../xtr-security) bundle registers on the main
dispatcher. At the request it matches the map, runs the matched firewall's chain — before
routing, so a request no route would answer is still challenged as a request — and parks the
matched firewall and its exception listener on the request's security state; a failure the
chain raises is announced on the exception event and answered by that listener, exactly once;
the finish of the request puts the stored listener away. A route documents its security with
the framework's own params; the firewall contributes no OpenAPI scheme of its own.

### Firewall listeners

A **`FirewallListenerInterface`** is one step of the chain a firewall runs over a request:
`supports(request)` tells whether the step handles the request — `False` skips it, while `None`
(lazy) and `True` (eager) both run `authenticate(request_event)`, which does the work and
typically answers by setting a response on the kernel's request event, which also stops the
chain. `get_priority()` declares the step's position — the higher, the earlier — and
**`AbstractListener`** is the template a concrete listener starts from: it fixes the default
priority `0` and leaves both hooks to the subclass. **`FirewallListenerOrder`** declares the
neighbours a listener runs `before` or `after` — a constraint that only reorders listeners
sharing a priority, and one that would cross it fails the build. The [xtr-security](../xtr-security)
bundle sorts each firewall's chain by them.

**`AuthenticatorManagerListener`** is the chain's authentication step: a thin delegation to a
firewall's authenticator manager — `supports` answers the manager's supports pass,
`authenticate` runs the pass that authenticates and sets the response a handler produced on the
event. The manager's two passes hand each other what they learned through the request's security
state, which rides the kernel event's bag: `authenticate` reads it off the event, while the
caller running the chain parks that bag on the request it asks `supports` about — the one place
both hooks reach the same carrier. **`TraceableAuthenticatorManagerListener`** wraps the
listener for the tooling: it re-parks the supporters the supports pass chose as traceable
wrappers, so what each authenticator answered is recorded and read through
`get_authenticators_info()`.

**`AccessListener`** is the chain's access step, at priority `-255` — after the authentication
step. `supports` matches the firewall's access map and parks what the matched rule requires on
the request's security state, answering `True` when there is something to decide and `None` —
the lazy join — when the match requires nothing or only public access; `authenticate` reads the
parked attributes back, decides the token from the token storage against them with the request
itself as the subject, and raises `AccessDeniedError` carrying the attributes, the subject and
the decision when it is refused. A null token stands in for an anonymous request, so the
decision — not the listener — is what turns an anonymous request away from a rule that needs
authentication.

### Authenticators, passports, badges and credentials

An **`AuthenticatorInterface`** answers `supports(request)` — `True` to handle and stop others,
`False` to skip, `None` to handle lazily (let a later authenticator try if this one yields no
token) — reads the request into a `Passport` with `authenticate(request)`, and mints a token
with `create_token(passport, firewall_name)`. `AbstractAuthenticator` is the base that builds a
`PostAuthenticationToken` carrying the user and roles.

A **`Passport`** gathers a `UserBadge`, a `CredentialsInterface` to verify for that user, and any
other `BadgeInterface` badges, keyed by class (`add_badge` — with an explicit key, so a custom badge
can stand in for a built-in — `get_badge`, `has_badge`, `get_user`, attributes). A badge
`is_resolved()` reports whether it has been handled; the manager fails a passport whose badges are
not all resolved once the check is done. The badges:

| Badge | Resolves when | Carries |
|---|---|---|
| `UserBadge(identifier, user_loader=None, ...)` | always | the identifier and how to load the user |
| `AuthenticationMethodBadge(*methods)` | always | the authentication methods the attempt verified |
| `CsrfTokenBadge(csrf_token_id, csrf_token)` | the CSRF listener checked the token | the token's identifier and the presented value |
| `PasswordUpgradeBadge(plaintext, upgrader=None)` | always | a verified plaintext to rehash and store |
| `RememberMeBadge(parameters=None)` | always | whether a remember-me cookie is wanted (`enable`/`disable`), and what to check |
| `PreAuthenticatedUserBadge()` | always | nothing — the user is already trusted |

A **`CredentialsInterface`** is a badge to verify: `PasswordCredentials(password)` holds a
plaintext (`get_password()`, `mark_resolved()` — reading it after resolution is refused, the
credential is consumed), `CustomCredentials(checker, credentials)` runs a callable through
`execute_custom_checker(user)`, which fails authentication unless it returns strictly `True`. A
**`SelfValidatingPassport`** carries no credentials, for an authenticator — like the access-token
one — that already trusts the credential; it attaches no `PreAuthenticatedUserBadge` of its own, so
the account checks still run.

### The authenticator manager and its event order

**`AuthenticatorManager(authenticators, token_storage, event_dispatcher, firewall_name, ...)`**
runs authentication for one firewall. `supports(request, state)` asks every authenticator,
parking the supporters and the skipped on the request's security state;
`authenticate_request(request, state)` reads that handoff back — once — and drives a fixed order
over the firewall's own dispatcher:

1. the first supporter that still applies reads the request into a passport;
2. **`CheckPassportEvent`** — listeners resolve the badges (load the user, verify the password);
3. every badge must report resolved, and every `required_badges` type must be present, else
   `BadCredentialsError`;
4. a token is created, then **`AuthenticationTokenCreatedEvent`** lets a listener replace it;
5. **`AuthenticationSuccessEvent`** ([core](../xtr-security-core)) runs the post-authentication
   account check;
6. the token is stored, the authenticator's success handler runs, and **`LoginSuccessEvent`** —
   carrying the token the storage held before the login — lets a listener migrate a password or
   replace the response.

Between the success handler and the login-success event, an authenticator that is an
**`InteractiveAuthenticatorInterface`** reporting `is_interactive()` announces the login through
**`InteractiveLoginEvent`** — a user actively logging in, as opposed to a session or a bearer token
re-establishing one — under the name `SecurityEvents.INTERACTIVE_LOGIN`. No authenticator shipped
here is interactive; one that is (a form login, a login link) brings the announcement with it.

A lazy authenticator that raises a plain `BadCredentialsError` is read as *no credential
presented* — it did not apply, so the next authenticator is tried. Any other failure is masked to
the configured `ExposeSecurityLevel` (`NONE` hides everything as bad credentials,
`ACCOUNT_STATUS` reveals disabled/locked/expired, `ALL` reveals the failure), answered by the
authenticator's failure handler and announced as **`LoginFailureEvent`** — never raised: a
response from the handler or a listener is returned for the firewall to send, and the lack of one
lets the request go on anonymous, where the access decision is what turns it into the entry
point's challenge. `AuthenticationSuccessHandlerInterface` and
`AuthenticationFailureHandlerInterface` are the two handler shapes a route may answer with, and
`authenticate_user(user, authenticator, request, badges=(), attributes=())` on the manager logs a
known user in through one authenticator outside the request-driven flow.

### Listeners

The bundle registers these on each firewall's dispatcher; they are the badge-resolving half of
the event order:

| Listener | Resolves |
|---|---|
| `UserProviderListener` | gives a `UserBadge` its loader from the firewall's user provider, unless it has one |
| `CheckCredentialsListener` | verifies a password passport's `PasswordCredentials` and `CustomCredentials` |
| `UserCheckerListener` | runs the account's pre- and post-authentication checks |
| `PasswordMigratingListener` | rehashes a password flagged by a `PasswordUpgradeBadge`, best-effort, storing through the badge's, the listener's, or the user provider's upgrader — a provider implementing `PasswordUpgraderInterface` is derived from the passport's user loader |

**The dummy-hash timing guard.** When a password passport names an *unknown* user,
`CheckCredentialsListener` still verifies against a dummy hash, so the timing of a bad username
and a bad password is the same — neither reveals which was wrong. The dummy is hashed once per
listener instance and kept, so no request pays the cost twice.

### Access map and request matchers

An **`AccessMap`** is an ordered list of rules: `add(request_matcher, attribute)` appends one,
`await get_patterns(message)` returns the first matching rule's attribute — as the one member of
a tuple — beside the channel it demands the request arrive over (`None` while no rule carries
one). An **`AccessListener(token_storage, access_decision_manager, access_map)`** is the chain
step that decides them: `supports` parks what the matched rule requires on the request's
security state and answers whether there is a decision to make, and `authenticate` reads it
back and decides the token from the token storage against it, with the request itself as the
subject, raising `AccessDeniedError` — carrying the attributes, the subject and the decision —
when it is refused. Until the chain runs the request, the same rules are decided the way the
firewall runner drives: `await check_access(message, token)` takes the token the runner
authenticated and short-circuits a public-access rule. The step sits at priority `-255`, after
the authentication step. A **`RequestMatcherInterface`** (from
[xtr-http-foundation](../xtr-http-foundation)) answers
`await matches(message)` over the request as a `ServerRequestInterface`:

| Matcher | Claims a request by |
|---|---|
| `PathRequestMatcher(pattern)` | its path (searched, not anchored; the mount prefix stripped and per-cent escapes undone) |
| `HostRequestMatcher(pattern)` | its host (matched case-insensitively) |
| `MethodRequestMatcher(methods)` | its method (empty `methods` claims every request) |
| `IpsRequestMatcher(ips)` | its client address (empty `ips` claims every request) |
| `ChainRequestMatcher(matchers)` | all of several matchers (an empty chain claims everything) |

This package keeps the escape hatch: **`CallableRequestMatcher(decide)`** defers the claim to a
callable `(message) -> bool`, for a rule none of the matchers above express.

### The context listener: a session's token, restored and written back

**`ContextListener(token_storage, user_providers, context_key, session_storage, *, logger=None,
dispatcher=None, trust_resolver=None)`** is the chain step a *stateful* firewall runs: it reads
the token the request's session carries — under the key `_security.<context>`, the firewall's
own name composed onto the prefix every user-facing key of the flow carries — and restores it
into the token storage, after refreshing the user it carries through the firewall's user
providers. `supports()` answers `None` always — the lazy join: nothing in a request's head
commits the listener, but a stateful firewall restores its context on every request. The step
sits at the default priority `0`, tied with the authentication step and ahead of the access
step, registered before the manager so the token is restored before anything reads it.

The refresh reloads the user through each provider that supports its class, in order, and
deauthenticates the token when the reload changed the user: the password changed (with the
legacy carve-out — a stored eight-character password that is the crc32c checksum of the
reloaded one is the same password), a role was granted or withdrawn, the identifier names
someone else, or a user comparing itself says so. Each reload is weighed by the listener's own
comparison and then announced as **`CheckRefreshedUserEvent`** — seeded with that verdict, for
a listener to confirm, add its own `AuthenticationError` reason to, or clear. A deauthentication
is announced as **`TokenDeauthenticatedEvent`** — the original token, the reason, the provider
classes that contributed, the error a listener gave — and the storage is left empty, so the
request goes on anonymous. A session holding no token, or something that is not one — a corrupt
payload, a foreign class — leaves the storage empty the same way, without failing the request.

The response half, **`on_response(response_event)`** — registered beside the chain on the
kernel's response event — writes the token back: what the request authenticated is stored under
the same session key, and an anonymous request's key is removed, so a logout does not linger in
the session. It runs only for the requests the request half marked with its own session key —
the firewall-run mark — so a response of a request another firewall ran is left to that
firewall's listener. The token is stored as the object it is: the session storage's own contract
owns the wire format, and the lazy-object initialisation guard the upstream listener opens with
has no lazy user to guard on this stack.

### The exception listener: 401, 403 and RFC 6750

**`ExceptionListener`** is a subscriber on the [xtr-http-kernel](../xtr-http-kernel) exception
event. It turns a security error raised while handling into the right response:

- an **`AuthenticationError`** becomes the firewall's entry-point challenge, or a bare `401`
  with `WWW-Authenticate: Bearer` when the firewall has no entry point;
- an **`AccessDeniedError`** from a caller who is not fully authenticated becomes the entry-point
  challenge for insufficient authentication; from a fully authenticated caller, a scope challenge
  (when the denied attribute is a scope), the firewall's access-denied handler, or a plain `403`;
- any other exception is left untouched, to whatever else handles it.

`AccessTokenAuthenticator` is itself an `AuthenticationEntryPointInterface`: `start(request,
error)` answers a request with an RFC 6750 bearer challenge, naming `invalid_token` when a
present token was rejected, and the `realm` when one is configured.

### Decorators

Five markers put the edge on a route, and stay out of the generated schema:

| Decorator | Does |
|---|---|
| `IsGranted(attribute, subject=None, *, message=None, status_code=None, exception_code=None, methods=(), consume_security_scopes=False)` | require an attribute, raising `AccessDeniedError` (or answering `status_code`) |
| `CurrentUser(user_class=None, *, optional=False, disabled=False)` | inject the current user; `optional` yields `None` when anonymous, `disabled` switches the resolution off |
| `CurrentToken(*, optional=False)` | inject the authenticated token; `optional` yields `None` when anonymous |
| `IsCsrfTokenValid(token_id, *, token_key="_token", methods=(), token_source=SOURCE_PAYLOAD)` | require the request to present the value minted for `token_id` |
| `IsGrantedContext` | the context a closure `IsGranted` attribute is handed (from [core](../xtr-security-core)) |

Every marker is pure metadata: the enforcement lives in an injectable service in
`resolver/` — `UserValueResolver`, `SecurityTokenResolver`, `IsGrantedChecker`,
`CsrfTokenChecker` — each built by hand from its constructor or filled from a
container, and each testable without the web framework. The thin dependency a
route carries delegates to them.

`IsGranted`'s `subject` is `None`, the name of a path parameter, or a callable used as a
dependency; its `attribute` is a string a voter matches or a callable
`(IsGrantedContext, subject) -> bool`. `methods` limits a check to those methods
(upper-cased; `GET` extends to `HEAD`); an empty list applies to every method.
`CurrentUser` raises `AuthenticationCredentialsNotFoundError` on an anonymous
request (a `401`), or `UnsupportedUserError` when the user is not of the
asked-for class — or of any of the classes, given a tuple. `CurrentToken` raises
the same on an anonymous request. `IsCsrfTokenValid` reads the presented value
from the sources its `token_source` bitmask names — `SOURCE_PAYLOAD` (the JSON
body, else the parsed form; the default), `SOURCE_QUERY`, `SOURCE_HEADER` — the
first named source that carries one — and refuses the request with a `403` when
the token manager does not vouch for it.

**The security scopes a route declares natively are never consumed silently.**
`IsGranted` ignores the request's accumulated `SecurityScopes` unless the route
opts in with `consume_security_scopes=True`; opted in, each accumulated scope is
decided through the voter stack too, as an `oauth2_scope(...)` attribute that
must be granted.
Without the opt-in, `Security(..., scopes=[...])` stays what declaring it alone
ever makes it: documentation.

### Deviations and decisions

- **No controller-arguments events.** The upstream listeners that enforce the
  route markers run on a controller-arguments event the
  [kernel](../xtr-http-kernel) deliberately lacks — the web framework resolves
  arguments. Enforcement here lives in the injectable services in `resolver/`,
  consumed by thin dependencies on the route: the same split, dispatched where
  this stack dispatches.
- **No expression language.** An `IsGranted` attribute or subject written as an
  expression, and an `IsCsrfTokenValid` id written as one, are not supported:
  the workspace ships no expression component. Strings and callables land;
  expression support is deferred until one exists.
- **`exception_code` is recorded, not applied.** The local error taxonomy
  carries no exception-code channel, so `IsGranted(exception_code=...)` is
  metadata a caller reads off the marker; the denial itself carries the
  attribute, the subject and the decision.
- **Nullability is stated on the marker.** The web framework does not hand a
  dependency the annotation of the parameter it fills, so `optional` on
  `CurrentUser`/`CurrentToken` states what `User | None` would declare, and the
  upstream argument-default rule translates to that same `optional`.
- **`IsCsrfTokenValid` answers `403` directly.** A request that fails the token
  check is refused with a plain `403` — the caller is already identified —
  rather than routed through the firewall's exception listener.

### Access tokens

An **`AccessTokenExtractorInterface`** pulls a bearer token out of a request; an
**`AccessTokenHandlerInterface`** turns a token string into a `UserBadge` with
`get_user_badge_from(token)`, raising `InvalidAccessTokenError` when it cannot be trusted. The
extractors:

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

Seven events are raised around a request's authentication — `CheckPassportEvent`,
`AuthenticationTokenCreatedEvent`, `InteractiveLoginEvent`, `LoginSuccessEvent`, `LoginFailureEvent`,
`CheckRefreshedUserEvent`, `TokenDeauthenticatedEvent`.
A subscriber listens to the event class itself (the dispatcher derives each event's name from its
class) — except `InteractiveLoginEvent`, the one event that carries a name of its own,
`SecurityEvents.INTERACTIVE_LOGIN` (`security.interactive_login`), because an application listens
for a user's own login across the whole flow rather than at one authenticator.
`SecurityEvents.ALIASES` maps every event class to the name it is dispatched under.

`CheckRefreshedUserEvent` and `TokenDeauthenticatedEvent` belong to the stateful half: the
context listener announces the first while refreshing the user a session token carries —
seeded with the verdict of its own comparison, for a listener to confirm, add a reason to,
or clear — and the second when the refresh deauthenticates, carrying the original token,
the reason, the providers that contributed and the error a listener gave.

## Errors

Everything this library raises derives from `SecurityError` (from
[xtr-security-core](../xtr-security-core)); authentication failures additionally derive from its
`AuthenticationError`, so one `except AuthenticationError` catches the token failures.

| Error | Base (besides `SecurityError`) | Raised when |
|---|---|---|
| `InvalidAccessTokenError` | `AuthenticationError` | a bearer token was present but could not be trusted — answered with an `invalid_token` challenge |
| `UnknownFirewallError` | `LookupError` | a firewall was asked for by a name none is registered under; carries `name` and `configured` |

## Layout

```
xtr_security_http/
├── firewall_map.py             FirewallMap, matched or fetched by name
├── firewall_context_interface.py  one firewall's runtime pieces
├── firewall/                   Firewall (the subscriber), AccessListener, ExceptionListener,
│                              ContextListener, RefreshUserResult, FirewallListenerInterface,
│                              AbstractListener
├── authentication/             AuthenticatorManager, handlers, ExposeSecurityLevel
├── authenticator/              AuthenticatorInterface, AccessTokenAuthenticator, passport/, token/
├── access_token/               extractors, handler interface, oidc/ (OidcTokenHandler)
├── oidc/                       DiscoveryOidcKeySetProvider
├── access_map.py               the ordered access-control rules
├── request_matcher/            the callable escape hatch (the rest come from xtr-http-foundation)
├── authorization/              OAuth2ScopeVoter, oauth2_scope, the scope-denied handler
├── decorator/                  IsGranted, CurrentUser, CurrentToken, IsCsrfTokenValid,
│                              FirewallListenerOrder
├── resolver/                   the enforcement services behind the markers
├── entry_point/                AuthenticationEntryPointInterface
├── event/                      the firewall events around a login
├── event_listener/             the listeners the bundle registers (incl. the timing guard)
└── exception/                  the errors this package adds
```

## In an application

This package works on its own and ships no bundle. The
[`xtr-security`](../xtr-security#use-in-an-application) bundle wires it — the firewalls, the
authenticators, the access map, the exception listener, the `Firewall` subscriber and the
`IsGranted`/`CurrentUser` surface — into an application on [xtr-dependency-injection](../xtr-dependency-injection), with
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
