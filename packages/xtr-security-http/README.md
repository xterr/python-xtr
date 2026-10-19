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
  turns it into a user. An OAuth2 handler introspects the token on the authorization server; an
  OIDC handler verifies a third-party issuer's tokens.
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
verifying and discovering an issuer's keys, and for verifying the signed introspection responses
the OAuth2 handler can ask for.

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

**`LogoutListener`** is the chain's logout step, at priority `-127` — behind the steps that
authenticate and decide, ahead of the ones that only clean up. A firewall with one configured
runs it where the firewall's insertion rule places it: ahead of the first chain step running at
a lower priority. `supports` answers whether the request's path is the configured logout path —
a strict `False` for anything else, so the chain skips it; `authenticate` proves the request
first (the cross-site request forgery token under the configured parameter name, in the
submitted form or the query string, when a manager is wired — `LogoutError` when it does not
check out), announces `LogoutEvent` on the firewall's own dispatcher, clears the token from the
storage and the request's security state, and sets the response a logout listener answered with
on the request's event, which also stops the chain. The event is announced before the token is
cleared, so its listeners still read the token being logged out.

**`SwitchUserListener`** is the chain's user-switch step, at the default priority `0` and
declared — through `@FirewallListenerOrder` — to run after the authentication step, so the
switch is carried out over a request the firewall has already authenticated. `supports` answers
whether the request carries the configured parameter naming the user to become — in its query
string, in the body of a request that is not safe, or in a header of the same name — or, when
the switch is scoped to a dedicated path, only at that path; `authenticate` proves the request
first (the forgery token under the configured parameter and id, when a manager is wired —
`AccessDeniedError` when it does not check out), then carries the switch out: the right to
switch is decided — the configured role, against the target user as the subject — the target
user is loaded beside a throwaway identifier no provider can know (and a target that cannot be
loaded burns a load of the current user instead, so a switch's timing never tells whether a
user exists), checked after authentication, and settled on a `SwitchUserToken` that keeps the
token the switch started from. The switch is announced as `SwitchUserEvent` under
`SecurityEvents.SWITCH_USER` before the token is stored — a listener may replace it — and the
request is answered with a redirect to the page it was asked at, the switch's own parameters
stripped from the address. The exit is the same parameter carrying `SwitchUserListener.EXIT_VALUE`
(`_exit`): the original token is restored, its user reloaded first, and the exit announced the
same way. A `stateless` step switches without answering the request.

### Logout

A logout is carried by the `LogoutEvent` — the request asking for it and the token it logs out —
announced on the firewall's own dispatcher, where each of the firewall's logout listeners does
its part. The first response set on the event is the one the request is answered with:

| Listener | Priority | Does |
|---|---|---|
| `DefaultLogoutListener` | 64 | answers a logout nothing else answered with a redirect to the configured target (`/` by default) — the first response wins |
| `ClearSiteDataListener` | 0 | sets the `Clear-Site-Data` header on the response, with the configured directives quoted and comma-joined, unless it already carries one |
| `CsrfTokenClearingListener` | 0 | clears every cross-site request forgery token the firewall's clearable storage minted |
| `SessionLogoutListener` | 0 | invalidates the session the request's security state carries — the one the context listener parked |
| `CookieClearingListener` | -255 | adds the `Set-Cookie` headers that clear the configured cookies, repeating the path and domain each was set with (`ClearedCookie`) |

**`LogoutUrlGenerator`** generates the logout addresses of the firewalls that registered one:
`register_listener(key, path, csrf_token_id, csrf_parameter, csrf_token_manager?, context?)`
records a firewall's logout, and `get_logout_path(key?)`, `get_logout_url(key?)` and
`get_logout_form(key?)` generate its path, its URL and the action and hidden fields of a form
posting to it — the form keeps the forgery token out of the address bar. A keyless generation
resolves its firewall from the token the storage holds (the firewall that authenticated it),
then the firewall named by `set_current_firewall`, then the one sharing the current context;
`reset()` puts that tracking back to none. Paths are literal — an absolute path or an absolute
URL, never a route name — and the URL runs the path through the injected URI builder, the path
itself by default.

The bundle's logout wiring — the configuration surface that builds the listener per firewall,
parks it on the context's `logout_listener` slot, registers the event listeners on the
firewall's dispatcher and registers each firewall with the generator — arrives with that
configuration surface; the pieces above are what it will wire.

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
re-establishing one — under the name `SecurityEvents.INTERACTIVE_LOGIN`. The form-login and
JSON-login authenticators are interactive — a login through either announces itself; a login link
brings the announcement with it when it lands.

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

### Login forms

**`AbstractLoginFormAuthenticator(http_utils)`** is the base a form login builds on: the subclass
names its login page's URL (`get_login_url(request)` — a path, compared strictly with the
request's own), `supports` answers only a POST to exactly that page, a failure keeps the error on
the request's session for the form that renders again and redirects back to the page, `start` —
the entry point — redirects there too, and `is_interactive()` reports the login as the user's own
act.

**`FormLoginAuthenticator(http_utils, user_provider, success_handler, failure_handler, options)`**
reads a submitted form by its configured names (`username_parameter`, `password_parameter`,
`check_path`, `post_only`, `form_only`, `enable_csrf`, `csrf_parameter`, `csrf_token_id`, and the
required `login_path`) into a passport carrying a `PasswordCredentials`, a `RememberMeBadge` and an
`AuthenticationMethodBadge` — plus a `CsrfTokenBadge` when `enable_csrf` is set, and a
`PasswordUpgradeBadge` when the provider upgrades passwords — and mints a `UsernamePasswordToken`.
It also implements `ReAuthenticationEntryPointInterface`: `start_re_authentication(request, token)`
sends an already-authenticated caller back to the form to prove themselves again, keeping their
identifier and the denied attribute on the session for the page.

**`JsonLoginAuthenticator(http_utils, user_provider, responses, success_handler=None,
failure_handler=None, options=None)`** is the stateless sibling: a JSON body read by its configured
paths (`username_path`, `password_path` — a dotted path walks a nested document), answered — when
no failure handler is given — with a `401` carrying the error's message as JSON. The password is
erased from the document before its fields ride along as remember-me parameters.

**`HttpBasicAuthenticator(realm_name, user_provider, responses, logger=None)`** authenticates the
`Authorization: Basic` header's credentials and is its own entry point: a `401` carrying
`WWW-Authenticate: Basic realm="…"`, which a failed attempt is answered with again.

The answers a form login gives are delegated. **`DefaultAuthenticationSuccessHandler(http_utils,
options=None, logger=None)`** redirects by its target ladder — the `target_path_parameter` the
request carried, the path the interrupted request saved on the session (read and removed — a
return trip happens once), the `Referer` when `use_referer` is set, then `default_target_path` —
and **`DefaultAuthenticationFailureHandler(http_utils, options=None, logger=None,
firewall_name=None)`** keeps the error on the session for the form that renders again and redirects
by its own ladder (`failure_path_parameter`, `failure_path`, then `login_path`), keeping the
`Referer` as the return trip's target when `use_referer` is set and the handler knows its firewall.
**`CustomAuthenticationSuccessHandler(handler, options, firewall_name)`** and
**`CustomAuthenticationFailureHandler(handler, options)`** are the seams for an application's own
handlers, handing them the wiring's options — and the firewall's name, for a success handler that
keys by one — through duck-typed setters.

**`AuthenticationUtils(request)`** reads what the last login attempt left, for the page that
renders the form again: `get_last_authentication_error(clear_session=True)`, `get_last_username()`
and `get_re_authentication_attribute()`, each reading the request's own security state first, then
the session. **`FallbackUserLoader(inner=None)`** wraps a user loader the wiring must not
override — a badge carrying one of these keeps it through the passport check, where a badge
with no loader gets the firewall's provider. The access-token authenticator carries the
replacement rule of its own for the badges its handlers build: a loader that is missing or
marked as a stand-in is replaced by the firewall's provider, when one is configured.

### Remember me

**`RememberMeDetails(user_identifier, expires, value)`** is the cookie's whole content: its
serialization — `:<b64url(identifier)>:<expires>:<value>`, the identifier in the URL-safe base64
alphabet, the expiry a Unix timestamp — is the format itself, and `from_raw_cookie` reads back
exactly what `str()` writes. **`RememberMeCookie`** is one cookie staged on the request's security
state under the `REMEMBER_ME_COOKIE` key, moved onto the outgoing head by
**`ResponseListener`** — a subscriber on the kernel's response event, registered on the
application's main dispatcher — which appends the finished `Set-Cookie` value the cookie renders
for itself.

A **`RememberMeHandlerInterface`** is the one voice on the cookie: `create_remember_me_cookie(request, user)`
stages it, `consume_remember_me_cookie(request, details)` spends it and loads its user,
`clear_remember_me_cookie(request)` stages its clearing. Every method takes the request, because
the cookie is staged on that request's own state — there is no request stack to read the current
one from. **`AbstractRememberMeHandler(user_provider, options, logger)`** loads the user a cookie
names and stages every cookie; its options default to the name `REMEMBERME`, a one-year lifetime,
`path=/`, `httponly`, and the two the conditions listener reads (`always_remember_me`,
`remember_me_parameter=_remember_me`). Two handlers complete it:

- **`SignatureRememberMeHandler(signature_hasher, user_provider, options, logger, clock)`** signs
  the value with the core `SignatureHasher` — checked against the identifier before the user is
  loaded, against the user's covered fields after — and reissues a fresh cookie on every consume.
  Stateless: no series can be revoked alone, only every cookie of the user, by changing what the
  signature covers.
- **`PersistentRememberMeHandler(token_provider, user_provider, options, logger, token_verifier,
  signature_properties, clock)`** stores each cookie's series and value — 33 random bytes each —
  through the core `TokenProviderInterface`, rotates the value on every consume (a spent value
  presented again raises the core `CookieTheftError`), skips the rotation within a 60-second
  window so concurrent requests do not spend one another, and binds a digest of the user's
  signature properties — the password by default, properties the user does not expose skipped —
  so a changed password retires the series. A verifier accepts a value the store no longer holds
  exactly; the provider itself is used when it implements the verifier's contract. Clearing drops
  the series the request's own cookie names.

Around the handlers: **`CheckRememberMeConditionsListener(options, logger)`** enables the passport's
`RememberMeBadge` on a successful login when the application always wants the cookie or the request
carries the remember-me parameter (the badge's own parameters first, then the request's attributes,
query, and body for a non-`GET`); **`RememberMeListener(handler, logger)`** — at a lower priority —
clears any cookie the request still carries and sets a new one when the badge was enabled, and
clears the cookie on a failed login, a logout and a deauthentication. **`RememberMeAuthenticator(handler,
token_storage, cookie_name, logger)`** spends the cookie a returning request presents: `supports`
answers `None` — lazily — for a request carrying the cookie and storing no token, `authenticate`
builds a self-validating passport whose user loader is the cookie being spent through the handler,
and the token is the core `RememberMeToken`, which a trust resolver tells apart from a fully
proven login. It reports itself interactive, as the flow always has.

### Login links

**`LoginLinkDetails(url, expires_at)`** is one minted link: the URL whole, and the moment the
hash inside it stops verifying. A **`LoginLinkHandlerInterface`** is the one voice on the
links: `create_login_link(user, request=None, lifetime=None, parameters=None)` mints one for
a user, and `consume_login_link(request)` checks the one a request presents and loads the
user it signs in.

**`LoginLinkHandler(user_provider, signature_hasher, options, uri_builder=None, clock=None)`**
signs stateless links with the core `SignatureHasher`: the hash covers the user, the expiry
and the link's extra parameters, and is checked against the identifier before the user is
loaded, then against the loaded user's own covered fields — so a changed password retires
every link issued before it, which is also the limit: no single link can be revoked alone.
The options are `lifetime` (600 seconds by default) and `path`, the literal path every
minted link leads to, required. Extra parameter names must match `[A-Za-z0-9_.-]+` and may
not take the reserved names `user`, `expires`, `hash` or `hash_parameters`; the extras are
sorted and their names listed in the link's `hash_parameters`, each covered by the hash.
Consuming reads the link's parameters from the query string, or the body of a request that
is not a `GET`; a refused link raises `InvalidLoginLinkError` — `ExpiredLoginLinkError`
when only its moment has passed — and the extra parameters it carried are parked on the
request's security state under the `LOGIN_LINK_PARAMETERS` key, for the handlers that
answer the login.

**`LoginLinkAuthenticator(login_link_handler, http_utils, success_handler, failure_handler,
options)`** spends the link a followed request presents: `supports` answers for the request
arriving at the configured `check_path` — a `POST` there when `check_post_only` is set —
and `authenticate` builds a self-validating passport whose user loader, wrapped in
`FallbackUserLoader` so the wiring leaves it alone, is the link being consumed through the
handler, wearing a `RememberMeBadge`. The answers are delegated to the success and failure
handlers, and the login reports itself interactive: the user followed the link themselves.

### Switch user

A user switch — one user temporarily acting as another, like the `su` command — is carried by
**`SwitchUserListener`** (see [Firewall listeners](#firewall-listeners)) and announced as
**`SwitchUserEvent`**: the request the switch was asked through, the user being switched to —
on an exit, the user returned to — and the token the switch settles on, which a listener may
replace through `set_token`. It runs under the name `SecurityEvents.SWITCH_USER`
(`security.switch_user`), announced once before the switched token is stored and once before
an exit restores the original.

**`ImpersonateUrlGenerator(config_lookup, token_storage, uri_builder=None,
csrf_token_manager=None)`** generates the addresses a switch is asked by:
`generate_impersonation_path(request, identifier, target_uri=None)` and its `..._url` twin,
`generate_exit_path(request, target_uri=None)` and its twin, and
`generate_impersonation_form` / `generate_exit_form`, answering the `ImpersonationForm` shape
the logout form has — the action, the hidden fields, the forgery field's name. The exit
addresses answer empty while the current user impersonates nobody, so a template can skip
them. How the request's firewall asks for switches is read through
**`SwitchUserConfigLookupInterface`** — `await get_switch_user_config(request)` answering the
firewall's **`SwitchUserConfig`** (the parameter name, the forgery toggle with its parameter
and id, the optional dedicated path) or `None` — the local stand-in for the bundle-level
firewall map the upstream generator reads, so whatever knows the firewalls can answer without
the generator knowing how they are held. A dedicated path carries the page to come back to as
an explicit `_target_path`; the URL methods write through the injected URI builder, which is
path-only by default. A generation over a firewall without a switch, a forgery-asking switch
without a manager, or a dedicated path configured as a route name raises
`ImpersonationError`.

### Pre-authenticated

Some requests arrive already vouched for — the server in front of the application authenticated
them, or a TLS certificate named their user. **`AbstractPreAuthenticatedAuthenticator(user_provider,
token_storage, firewall_name, logger=None)`** is the base those authenticators share: a subclass
implements `extract_username(request)` — the one abstract part, reading the username the request
carries as already proven — and the base decides the rest. `supports` skips a request whose
reading yields no user, one whose reading raises `BadCredentialsError` (clearing the token the
failure invalidates), and one whose user already holds a `PreAuthenticatedToken` for this
firewall: the token from the session vouches for everything a new one would. `authenticate`
builds a self-validating passport whose user loader is the provider's `load_user_by_identifier`,
wearing a `PreAuthenticatedUserBadge` — the badge that tells the passport check there are no
credentials to verify and the account was vouched for before the passport existed. The token it
settles on is the core `PreAuthenticatedToken`, a failure clears the firewall's pre-authenticated
token and answers nothing, and the login reports itself interactive.

**`RemoteUserAuthenticator(user_provider, token_storage, firewall_name, user_key="REMOTE_USER",
logger=None)`** reads the account a server in front authenticated, from the environment the
request arrives with: a request whose environment carries no `user_key` is refused, and one whose
value is empty reads as no user. **`X509Authenticator(user_provider, token_storage,
firewall_name, user_key="SSL_CLIENT_S_DN_Email", credentials_key="SSL_CLIENT_S_DN", logger=None,
credential_user_identifier="emailAddress")`** reads what the server verified of the request's
client certificate: the email key first, as it is, and the configured identifier out of the
distinguished name when the email is not there — `emailAddress` also answers its dotted OID
spelling `1.2.840.113549.1.9.1`, a custom identifier is matched anywhere in the name, and the
value read out of a name is trimmed. A request carrying neither key, or a name without the
identifier, is refused.

### Listeners

The bundle registers these on each firewall's dispatcher; they are the badge-resolving half of
the event order:

| Listener | Resolves |
|---|---|
| `UserProviderListener` | gives a `UserBadge` its loader from the firewall's user provider, unless it has one |
| `CheckCredentialsListener` | verifies a password passport's `PasswordCredentials` and `CustomCredentials` |
| `CsrfProtectionListener` | settles a passport's `CsrfTokenBadge` — the token manager must vouch for the value the request presented, or the login fails |
| `UserCheckerListener` | runs the account's pre- and post-authentication checks |
| `PasswordMigratingListener` | rehashes a password flagged by a `PasswordUpgradeBadge`, best-effort, storing through the badge's, the listener's, or the user provider's upgrader — a provider implementing `PasswordUpgraderInterface` is derived from the passport's user loader |
| `SessionStrategyListener` | nothing on a passport — hands a successful login to the firewall's session strategy, which moves the session the request reattached |
| `CheckRememberMeConditionsListener` | nothing on a passport — enables the `RememberMeBadge` when the login asked to be remembered |
| `RememberMeListener` | nothing on a passport — clears any cookie the request carried and sets the one the enabled badge earned; clears it on a failure, a logout, a deauthentication |
| `LoginThrottlingListener` | nothing on a passport — refuses an attempt already over the login limits, counts a failed one, forgets the account's count on a successful one |
| `AuthenticationProofsListener` | nothing on a passport — records the authentication methods an interactive, non-remember-me login proved on its token, and carries the previous token's proofs over for the same user |

The logout listeners — the ones answering `LogoutEvent` rather than a passport — have their own
table under [Logout](#logout); the bundle's wiring for them arrives with the logout configuration
surface. The remember-me pair runs on the login-success event at the priorities above; the
response listener that moves the staged cookie onto the response belongs to the kernel's response
event, on the application's main dispatcher.

**Login throttling.** The throttling listener runs first of all on the passport check (priority
2080, above the provider listener's 2048), and answers through one request limiter —
`RequestRateLimiterInterface` from [xtr-http-foundation](../xtr-http-foundation), a peekable one
preferred. The limiter builds its own keys, and the default one —
`DefaultLoginRateLimiter` in `rate_limiter/`, over the [xtr-rate-limiter](../xtr-rate-limiter)
factories — counts a login twice: under the address it came from (a global limit, bounding how
many accounts one client may sweep) and under the account it named from that address (a local
limit). Both keys are eight-character HMAC-SHA256 prefixes over a non-empty application secret,
so a store shared across servers keeps no readable account or address; a successful login forgets
the local count only — the global one must survive the successful login of any one account. A
peekable limiter is looked ahead at on the check (nothing spent), counted on a failure; a
non-peekable one is counted on the check and still forgotten on a success. An attempt over the
limit is refused with the core `TooManyLoginAttemptsAuthenticationError`, carrying the minutes to
wait, and announced as a `RateLimitExceededEvent` on the dispatcher the listener was given.

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
request goes on anonymous. A switch token refreshes from the inside out: the original token —
the impersonator's — is refreshed first, and a reload that deauthenticates it deauthenticates
the switch with it, because a switch whose origin is gone has nothing to return to. A session
holding no token, or something that is not one — a corrupt
payload, a foreign class — leaves the storage empty the same way, without failing the request.

The response half, **`on_response(response_event)`** — registered beside the chain on the
kernel's response event — writes the token back: what the request authenticated is stored under
the same session key, and an anonymous request's key is removed, so a logout does not linger in
the session. It runs only for the requests the request half marked with its own session key —
the firewall-run mark — so a response of a request another firewall ran is left to that
firewall's listener. The token is stored as the object it is: the session storage's own contract
owns the wire format, and the lazy-object initialisation guard the upstream listener opens with
has no lazy user to guard on this stack.

### The session strategy: what a login does to the session it reattached

A login is the moment a session's ID is most worth stealing, and
**`SessionAuthenticationStrategy(strategy, csrf_token_storage=None)`** is what the login does
about it, under the strategy the firewall configured — `SessionAuthenticationStrategy.NONE`
keeps the session as it is, `MIGRATE` carries its attributes to a fresh ID and destroys the
entry under the old one (`session.migrate(destroy_old=True)`, so a session fixation stops
answering for the account the login just named) and clears the clearable CSRF token storage
with it, so a token value stolen before the rotation cannot answer after it, and `INVALIDATE`
empties the session entirely. An unknown strategy name is refused when the strategy runs —
`InvalidSessionStrategyError`, carrying the name as configured. The strategy moves the session
the request's security state carries — the context listener's park — so the ID it rotates is
the ID the response half writes the token back under; a request whose state holds no session
is refused with `MissingSessionError` rather than silently rotated around.

**`SessionStrategyListener(session_authentication_strategy)`** hands a successful login to
that strategy: a subscriber on `LoginSuccessEvent`, on the firewall's own dispatcher, that
skips a login with no session to move — a stateless firewall, or a request no stateful chain
ran — and a re-authentication of the same account, where the previous token names the same
non-empty user identifier and is of the same class as the new one: the session already answers
for this account, and rotating it would log out the very login it celebrates. The upstream
guard is the request's *session cookie* — a request that reattached no session is skipped —
which the local session keeps private; a session made fresh for the request migrates too,
harmlessly, since its storage entry is empty and nothing stored travels with it.

### The channel listener: the scheme a rule demands

**`ChannelListener(access_map, responses, bridge, *, logger=None, http_port=80,
https_port=443)`** is the chain step that moves a request onto the scheme its matched rule
demands it arrive over. `supports` asks the access map — the same rules the access step
decides attributes from — and answers `True` when the matched rule demands `https` of a
request that arrived over plain `http`, or `http` of one that arrived encrypted; every other
answer — no rule matched, the rule demands no channel, the request already carries the
demanded one — is `False`, the strict skip: the step parks nothing, so a request with nothing
to change has nothing to come back for. `authenticate` answers the request with a **301** to
the same request over the demanded scheme: the host, the whole path and its query string kept,
the port the *target* scheme is configured to answer on spelled out only when it is not that
scheme's default (`http_port` for `http`, `https_port` for `https`), and the port the request
itself arrived on left behind — the target scheme has a port of its own.

The scheme a request is read by is its URI's own — the connection's answer, not a forwarded
header's claim; this stack has no trusted-proxy machinery to weigh one. A proxy that
terminates the encryption in front of the server therefore leaves the request reading plain,
and the redirect this step builds would loop — the step's log names the `X-Forwarded-Proto`
and `Forwarded` headers when they claim the request was encrypted already. The step sits at
the default priority `0`, tied with the authentication step and ahead of the access step. No
rule the bundle builds carries a channel today, so no chain the bundle wires runs it yet.

### The exception listener: 401, 403 and RFC 6750

**`ExceptionListener`** is one object per firewall, built from that firewall's parts — its
name, its entry point, its access-denied handler — and parked by the firewall on the
request's carrier, so a request's failure is answered by the firewall that ran it. It turns a
security error raised while handling into the right response, walking the failure's chain
of causes to the first one it owns:

- an **`AuthenticationError`** becomes the firewall's entry-point challenge, or a bare `401`
  with `WWW-Authenticate: Bearer` when the firewall has no entry point. The path the request
  was heading for is kept on the session for the return trip — unless the firewall is
  stateless, or the entry point only stands in (a
  `FallbackAuthenticationEntryPointInterface`) — and an account-status error clears the
  token, so a disabled account cannot loop its own challenge;
- an **`AccessDeniedError`** from a caller who is not fully authenticated becomes the entry-point
  challenge for insufficient authentication — naming the masked authentication error the
  manager parked, when one was; from a fully authenticated caller, a fresh proof may be
  asked through a `ReAuthenticationEntryPointInterface` when a recency vote asked for one
  (the asked attribute parked under the re-authentication key), else a scope challenge (when
  the denied attribute is a scope), the firewall's access-denied handler, or a plain `403`;
- any other exception is left untouched, to whatever else handles it.

The upstream error page — a sub-request rendering a denial — has no local counterpart: this
kernel has no sub-request mechanism, so the `error_page` parameter is kept for the surface
that will carry it and a configured page is not rendered; the refusal chain falls through to
the plain `403`. The target path is kept under `_security.<firewall>.target_path` by the
`util` helpers `save_target_path`, `get_target_path` and `remove_target_path`, over the
session and the firewall's name.

`AccessTokenAuthenticator` only stands in as an entry point (a
`FallbackAuthenticationEntryPointInterface`): `start(request, error)` answers a request no
authenticator applied to with the RFC 6750 bearer challenge — the `realm` when one is
configured, the protected-resource metadata address when one is, and the scheme and
parameters of the sender constraint when one is configured. The challenge of a request
that carried no token at all holds no error code; a token that was rejected is answered by
the authenticator's own failure hook, with `invalid_token`.

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

- **The OIDC discovery reader is async where its upstream twin is not.** The
  cache contract here is awaitable — a fetch-or-compute over I/O — so
  `get_secure_endpoint` and `get_issuer` are `async def` where the upstream
  reader answers synchronously from a memoized document. Callers await them;
  the semantics are the upstream ones.
- **`OidcDiscovery.prefetch` cannot probe the cache.** The cache contract
  offers no read that computes nothing, so a prefetch sends its request
  unconditionally (unless a response is already in flight or the document
  memoized) where the upstream one stays quiet when the entry is warm; the
  prefetched response is dropped unread when the cache answers a warm entry,
  exactly as upstream drops it.
- **The discovery reader caches unconditionally.** The upstream reader skips
  saving when the URL that served the document is unknown; the cache contract
  here has no "do not keep" answer for a computed value, so the entry is saved
  with the URL it was served by, empty or not.
- **The discovery key-set provider keeps a no-op `aclose`.** The provider no
  longer owns an HTTP client — the application's is injected — so it holds
  nothing to release; the method stays so the wiring that collects closeable
  providers needs no special case.
- **The discovery key-set provider serves stale keys no longer.** The rebuilt
  provider keeps its keys in the injected cache, whose expiry is the
  provider's freshness boundary; the in-memory `max_stale` ceiling and the
  cold-start failure memo of the previous design went with it, as did the
  same-origin `jwks_uri` check — the aligned discovery weighs the announced
  endpoint's scheme and the issuer the document announces instead, which is
  the upstream shape.
- **The OIDC client omits the DPoP seam.** The upstream client takes an
  optional proof factory and asks for a bound access token when one is given;
  the proof machinery is deferred here, so the client always asks for a
  bearer token and the single-retry hook stays the access token type's
  `on_response` — which the bearer type answers `False`.
- **The OIDC login tracks its pending attempts in an index attribute.** The
  upstream authenticator enumerates the session's attribute names to find
  its pending attempts; the local session contract exposes no enumeration,
  so the states are kept in a list under
  `_security.oidc_login.<firewall>.attempts`, oldest first, and the attempt
  keys are derived from it. The cap (five, oldest dropped first), the
  constant-time state match and the consume-on-callback semantics are the
  upstream ones, pinned by tests.
- **The OIDC login validates the ID token against `get_issuer()`.** The
  upstream authenticator reads the issuer straight off the discovery
  document's configuration; the local one goes through
  `OidcDiscovery.get_issuer()`, which requires an expected issuer to have
  been configured — a discovery document nobody vouched for cannot name the
  audience of the flow. The value validated against is the same one.
- **The OIDC login's redirects answer through `HttpUtils`.** The upstream
  entry point returns a bare redirect response; the local one goes through
  `create_redirect_response`, so a configured domain regexp weighs the
  provider's authorization endpoint too — a further restriction, never a
  widening, and the family's convention.
- **The OIDC login folds the upstream's logic exceptions into
  `InvalidArgumentError`.** The upstream constructor guard raises an
  invalid-argument exception and the runtime guards (a listener setting a
  managed parameter, a public client without PKCE or a signature verifier)
  a logic one; the local taxonomy has no separate logic-error class, so all
  four raise `InvalidArgumentError`, and a request without a session raises
  `MissingSessionError` — the stateful family's refusal.
- **The ID token reader validates claims itself.** The upstream reader leans
  on the JOSE library's claim-checker manager for `iss`/`aud`/`exp`/`iat`/`nbf`
  and hand-writes the OIDC-specific rules (`sub`, `azp`, `nonce`, `max_age`).
  The local JOSE library does have a claims registry — its clock is injectable
  and its leeway maps to the allowed drift — but it reads a time claim with a
  bare `isinstance(value, (int, float))`, which accepts `true` as the timestamp
  `1` where the upstream check refuses it; it dispatches per claim in the
  token's document order, where which error a multi-defect token surfaces
  first follows the manager's fixed checker order upstream and does here; and
  its terse library errors would need translating into the reader's texts
  regardless. The rules are written out against the injected clock: the same
  set, in the same fixed order, with the same refusal of a non-numeric time
  claim.
- **No controller-arguments events.** The upstream listeners that enforce the
  route markers run on a controller-arguments event the
  [kernel](../xtr-http-kernel) deliberately lacks — the web framework resolves
  arguments. Enforcement here lives in the injectable services in `resolver/`,
  consumed by thin dependencies on the route: the same split, dispatched where
  this stack dispatches.
- **No expression language.** An `IsGranted` attribute or subject written as an
  expression, and an `IsCsrfTokenValid` id written as one, are not supported:
  the workspace ships no expression component. `IsGranted`'s attribute and
  subject accept strings and callables; an `IsCsrfTokenValid` id is a plain
  string — the expression and callable forms it takes upstream are not ported.
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
- **`failure_forward` is refused.** The default failure handler answers with
  the redirect only: this stack has no sub-request to hand the login page to,
  so a configuration asking for the forward is a wiring mistake reported where
  it would cost a request, not a request answered as if it had been forwarded.
- **A malformed form field fails the login, not the request.** A username or
  password that is missing, empty or not a string at all raises
  `BadCredentialsError` — the failure handler answers it — where the upstream
  stack answers some of them with a bare `400`: no HTTP-status distinction
  lives in this stack's error taxonomy, and a form login is a form answered,
  not an API request rejected.
- **The `Referer` is weighed by path.** The URI builder is path-only (no
  routing component), so the pages a referer must not win — the login page,
  the page the request asked for — are recognised by their paths, and the
  failure handler's save checks the referer's host against the request's own.
- **`FormLoginAuthenticator` requires a `login_path` option.** Upstream's
  bundle config guarantees one; here the constructor refuses to build without
  it, where upstream would fail later on a missing array key.
- **`JsonLoginAuthenticator` and `HttpBasicAuthenticator` take a response
  factory.** Upstream constructs its `JsonResponse`/`Response` directly; here
  the class names no response class, so the factory is a constructor parameter.
- **The throttling listener reads the request off the passport event.** Upstream
  reaches the current request through a request stack, and parks the username
  on the request's mutable attributes; here `CheckPassportEvent` carries the
  request (the manager passes it), and the username is parked on the request's
  security state — the per-request carrier — because a request message here has
  no mutable attributes. The exceeded-rate-limit event is normalised into the
  rate-limiter package's `RateLimit` value object, which is the state its
  constructor declares, rather than passing a third-party limiter's own answer
  through unchecked.
- **The remember-me handlers take the request.** Upstream pulls the main request from a request
  stack; this stack has none, so every handler method takes the request the flow is running and
  stages the cookie on that request's own security state.
- **The staged cookie is a value object, rendered where it is read.** Upstream stages a framework
  `Cookie` and the response listener sets it on the response; here the staged `RememberMeCookie`
  renders its own finished `Set-Cookie` value — through the [foundation](../xtr-http-foundation)
  cookie helpers — and the response listener appends it to the outgoing head. The response
  listener keeps no main-request guard: this kernel has no sub-requests.
- **The persistent handler reads properties, not property paths.** Upstream walks `foo[bar]`
  paths through a property accessor; here a signature property is a plain attribute name read
  with `getattr`, the same reading the core `SignatureHasher` does.
- **The remember-me parameter is a plain name.** Upstream evaluates `foo[bar]` paths against the
  request; the conditions listener reads one name — the badge's parameters first, then the
  request's attributes, query, and body for a non-`GET`.
- **An unsupported user class is not logged by the authenticator.** Upstream's
  `RememberMeAuthenticator` logs `UnsupportedUserException` at warning; the local
  `UnsupportedUserError` derives from `SecurityError` and `TypeError`, never from
  `AuthenticationError`, so it cannot reach the failure hook and the branch has no local
  counterpart.
- **Login links lead by a literal path, not a route name.** Upstream generates the link's
  URL from a route name through a routing component this stack does not have; the handler's
  `path` option and the authenticator's `check_path` name the literal path, a `route_name`
  or `check_route` option is refused, and the URI a path becomes is written by the injected
  URI builder — the path itself by default, and the builder receives the request the link
  is generated against, the translation of building the link for that request's own
  address.
- **The login-link notification is not ported.** Upstream's `LoginLinkNotification` wraps
  a minted link for a notifier component this workspace does not ship; sending the link is
  the application's own.
- **A non-string `user` parameter is refused as missing.** Upstream would hand a repeated
  query parameter's array to the badge and fail later; the local authenticator answers the
  same "Missing user from link." error for a value that is not a string.
- **The switch listener takes its HTTP utilities and a bridge as required parameters.**
  Upstream takes its HTTP utilities optionally — needed only with a dedicated path — and
  builds the non-path redirect directly; here they are the one redirect builder — the
  class names no response class — and the bridge converts the built message into what the
  kernel's event accepts, so both are constructor parameters.
- **The switch's target route is not ported.** Upstream can redirect a completed switch to
  a configured `target_route` through a routing component; no routing component exists here,
  so the redirect falls to the request's own stripped URI — or the submitted `_target_path`
  and then `/` on a dedicated path — and the generator refuses a dedicated path configured
  as a route name.
- **The query strip is written on the URI's text.** Upstream removes the switch's parameters
  from the request's query bag and rebuilds the query string; a request message is immutable
  here, so the strip removes each parameter's pattern from the URI text and mends the join,
  keeping the spelling the client sent for the parameters that remain.
- **The burned identifier is hashed with the standard library.** Upstream derives its
  timing-equalisation identifier with its own 128-bit hash; here SHA-256 over random bytes
  serves the same purpose — an unguessable identifier no provider can know — without a
  hashing dependency.
- **The impersonate generator takes the request as a parameter.** Upstream reads the
  current request from a request stack; this stack has none, so every generate method
  takes the request it generates for, and the URL methods write through the injected URI
  builder — the path itself by default, an absolute URL when the application's builder
  writes one.
- **The generator reads the firewall's switch configuration through a local interface.**
  Upstream reaches into the bundle's own firewall map; here
  `SwitchUserConfigLookupInterface` answers the switch-user configuration of the request's
  firewall — or `None` — so whatever knows the firewalls can answer, and the generator
  works with no bundle behind it.
- **A non-string switch parameter reads as no username.** Upstream would hand a repeated
  query parameter's array on and fail later; the local readers narrow to text, so anything
  but a name is not a switch this flow can carry out.
- **The pre-authenticated username is read twice, not handed over.** Upstream parks the
  username its supports pass extracted on the request and reads the park back when
  authenticating; a request message is immutable here, and the pass that authenticates is
  handed the request as it arrived — not the one the supports pass read — so
  `authenticate` reads the request again through the same `extract_username` hook. The
  reading is the request's own environment, so it answers what it answered before.
- **The access-token authenticator answers lazily on a tokenless request.** Upstream's
  `supports` answers `False` when its extractor finds no token, collecting the reason for
  the tooling; the local extractor's read is async and the supports pass is sync, so the
  miss cannot be answered there without inventing a synchronous reading the extractor
  contract does not carry. The miss is answered one step later — `authenticate` raises the
  no-token error and the manager's lazy abstain skips the authenticator — which leaves the
  request anonymous exactly as a `False` would.
- **A marked user loader is the wiring's word, not the authenticator's.** The
  `UserProviderListener` leaves a `FallbackUserLoader`-marked loader alone — the marker's
  word to the wiring — while the access-token authenticator replaces a marked loader with
  the firewall's provider when one is configured, the rule the upstream authenticator
  itself carries: a handler that knows how to load its own user marks its loader so the
  wiring keeps it, and a stand-in loader is the provider's to replace.
- **The introspection handler reads the members as they are spelled.** Upstream re-cases every
  claim name before building the user; the local `OAuth2User` speaks RFC 7662's own spelling
  (`client_id`, `updated_at`), so the members keep the names the response carried and the
  normalisations — the `updated_at` moment, the two verified flags — read the response's
  spellings too.
- **`enable_signed_response` requires its key set.** Upstream accepts none because its
  discovery variant fills the keys from the authorization server's metadata; that discovery
  machinery is the OIDC discovery alignment's, so until it lands the key set is a required
  argument and the discovery setter is not ported.
- **An empty algorithm allow-list is refused.** The JOSE library reads an empty allow-list as
  *no restriction*, so a handler configured without algorithms would verify a signed response
  against anything; the setter refuses the empty list rather than silently disabling the
  restriction.
- **The OIDC errors end in `Error`, not `Exception`.** The local convention names every error
  the package raises with the `Error` suffix, so the OIDC family's `InvalidSignatureError` and
  `MissingClaimError` follow it; both derive from the core `AuthenticationError`, as their
  upstream counterparts do from the authentication exception.
- **`InvalidSignatureError` is raised by nothing yet.** Upstream's verifier-side OIDC handler
  raises it on a bad signature; the local one landed earlier and reports the same failure as an
  `InvalidAccessTokenError` directly, so the error completes the family's surface — the
  signature-verification side names it — without a raiser of its own.
- **The generator takes an algorithm allow-list, not an algorithm manager.** The JOSE library
  signs by the header's `alg`, so the manager's list becomes a sequence of names the generator
  validates a chosen algorithm against; the signing key is chosen with the library's own key-set
  selection, which picks among the suitable keys rather than the first.
- **The userinfo handler rides the `oidc` extra.** It needs no JOSE library — only the HTTP
  client and cache contracts — but it lives in the OIDC subpackage, whose import gate requires
  the extra; an application using only the userinfo handler installs it anyway.
- **The userinfo handler fetches its own discovery document.** Upstream delegates to a discovery
  reader the local side does not have yet — the OIDC discovery alignment owns it — so the
  handler reads the well-known document itself, through its own client and cache, and weighs the
  announced endpoint against the URL that served the document exactly as that reader would.
  When the alignment lands, the fetch moves behind it.
- **The userinfo handler keeps no memo to reset.** Upstream memoizes the decoded document per
  instance and resets it between requests; here the cache is the memo — every token reads it,
  as the introspection handler reads its own — so there is nothing to reset and no reset hook.
- **The trait refuses with the access-token error.** Upstream's shared behaviour throws a
  generic runtime error its handlers wrap; here it raises `InvalidAccessTokenError` directly —
  the failure currency of the access-token handlers it serves — which those handlers log and
  re-raise as-is.
- **The client suite's audience is an issuer string, not a discovery reader.** Upstream's
  `AbstractClientAssertion` takes a discovery object and reads its issuer; the discovery
  reader is the OIDC client alignment's own deliverable, so the local base takes the
  issuer identifier outright — a caller that has a reader hands its `issuer` over, and
  nothing here knows the reader.
- **The MAC key length is measured, not exercised.** Upstream signs once with the secret
  at construction to surface one its library rejects; the local JOSE library warns where
  the upstream one refuses, so `ClientSecretJwt` measures the RFC 7518, Section 3.2
  minimum — as many bytes as the digest produces — itself.
- **The PKCE refusal is an invalid argument.** Upstream answers a code exchange without
  a verifier with a logic exception; the local error taxonomy carries no logic error, and
  the refusal names a call missing its `code_verifier`, so it raises
  `InvalidArgumentError` — a malformed call.
- **The assertion's default `typ` is suppressed.** The local JOSE library adds
  `typ: JWT` to a header that names none; upstream's builder adds nothing, so the local
  assertion is typed only when it names the issuer.
- **The algorithms map names key types, not algorithm classes.** The local JOSE library
  selects an algorithm by its JWA name, so `JwsAlgorithms` maps each name onto what it
  demands of its key — the key type, and the curve for ECDSA — which is what
  `check_key` reads.
- **DPoP is deferred.** Upstream's `OAuth2/` also carries a DPoP token type (with
  per-origin nonce memory and a retry on `use_dpop_nonce`) and a proof factory; neither
  is landed here. The follow-up that lands them is the plan's deferred DPoP row, and the
  client this suite serves works bearer-only until then.

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

**`AccessTokenAuthenticator(handler, extractor, user_provider=None, ..., realm=None,
resource_metadata_uri=None, sender_constraint=None)`** reads the token, validates it through
the handler, and builds a `SelfValidatingPassport`; it copies the badge's granted scopes —
read from its `scope` or `scp` attribute, the first that reads — onto the token as
`oauth2_scope`. A `sender_constraint` (a `SenderConstraintInterface`) weighs the request
against what the token says it is bound to before anything is loaded on the user's behalf,
and names the scheme and the parameters every challenge answers with; a failed
authentication is always answered — a `401` whose `WWW-Authenticate` names `invalid_token` —
and the `resource_metadata_uri` (RFC 9728) is advertised in every challenge, a path
resolved against the request.

### OAuth2 introspection

**`Oauth2TokenHandler`** (in `access_token/oauth2/`) validates a bearer token the only way a
resource server can trust one it did not issue: it asks the authorization server (RFC 7662).
The endpoint is reached through the HTTP client the handler is given — a scoped client whose
`base_uri` is the introspection endpoint and whose `auth_basic` carries this resource server's
credentials, so the handler knows nothing of the transport:

```python
from xtr_http_client import HttpxHttpClient
from xtr_security_http.access_token.oauth2 import Oauth2TokenHandler

handler = Oauth2TokenHandler(
    HttpxHttpClient().with_options(
        base_uri="https://as.example/introspect",
        auth_basic=("resource-server", "secret"),
    ),
    audiences="shop-api",
    issuer="https://as.example",
)
```

The constructor takes the client, an optional logger, the `audiences` this resource server
answers for, the `issuer` of the authorization server, the `claim` the user identifier is read
from (`sub` with `username` falling back by default), a clock and the `allowed_time_drift` on
the time members. Only `active`, `exp`, `nbf`, `iat`, `iss` and `aud` are read — the last two
only when the handler was given the ones it expects — and the badge carries the identifier, a
loader that builds the core `OAuth2User` the response describes, and the members themselves as
the badge's attributes, so the access-token authenticator reads the granted scopes out of them.
Every failure becomes an `InvalidAccessTokenError` whose public text is `Invalid credentials.`
— the specific reason is logged and chained.

`enable_cache(cache, key_prefix, ttl=60)` keeps the responses of active tokens for at most
`ttl` seconds — never past the `exp` the server reported, and an inactive response is not
cached at all. Entries are keyed by the digest of the token, so a pool holds no usable
credential. `enable_signed_response(algorithms, keyset=None, enforce=True)` asks for the
response as a signed JWT (RFC 9701) and verifies it — the `typ` header, the signature against
the key set under the algorithm allow-list, the mandatory top-level claims, and the RFC 7662
members nested inside `token_introspection`; it needs joserfc, which the `oidc` extra carries.
The verifying keys may also be read from the authorization server's metadata instead of a
pinned key set: `enable_signed_response_discovery(cache, client, cache_key)` builds an
`OidcDiscovery` over the RFC 8414 metadata URL derived from the handler's `issuer` (required
for that path), keeps the document under `cache_key + ".document"` and the keys under the bare
`cache_key` for what the response headers' freshness arithmetic leaves, and a `keyset` of
`None` then resolves to those keys.

### OAuth2 clients

The `oauth2/` folder at the package root is the **client** side of OAuth2 — what an
application that *talks to* an authorization server builds its client from. It is a
different folder and a different concern from `access_token/oauth2/`, which is the
resource server validating the tokens that arrive: this one never reads a token it was
not issued.

A **`ClientAuthenticationInterface`** is how a client authenticates itself at the token
endpoint — the one method its registration carries, named by RFC 7591, Section 2 in its
`token_endpoint_auth_method` metadata. `authenticate(client_id, token_endpoint, options)`
returns the request options the token request is made with — a header, a body member, or
nothing at all — and `get_method()` answers the registration name, compared exactly:

| Method | Does |
|---|---|
| `ClientSecretBasic(secret)` | sends the identifier and secret as Basic credentials, each percent-encoded |
| `ClientSecretPost(secret)` | adds `client_secret` to the token request body |
| `ClientSecretJwt(secret, algorithm="HS256", lifetime=60, clock=None, issuer=None)` | signs a jwt-bearer assertion (RFC 7523) with the secret as its HMAC key |
| `PrivateKeyJwt(key, algorithm="RS256", lifetime=60, clock=None, issuer=None)` | signs the assertion with the client's private key |
| `NoClientAuthentication()` | sends nothing — a public client, which refuses a code exchange without a PKCE verifier |
| `TlsClientAuth()` / `SelfSignedTlsClientAuth()` | authenticates by the certificate the TLS handshake presented; the certificate itself is configured on the HTTP client (`local_cert`, `local_pk`, `passphrase`) |

The assertion pair builds on `AbstractClientAssertion`: the assertion names the client as
its issuer and subject, the provider as its audience — the `issuer` given to the
constructor, or the token endpoint — carries a single-use `jti`, an `iat` read from the
clock and an `exp` a `lifetime` past it, and is typed `client-authentication+jwt` only
when it names the issuer. `JwsAlgorithms` maps the JWA names onto what each demands of
its key (`check_key`), and the allow-lists keep a shared secret out of `private_key_jwt`
and an asymmetric key out of `client_secret_jwt`.

An **`AccessTokenTypeInterface`** is how the token the endpoint issued is presented:
`get_token_type()`, `check_token_response(members)` — which refuses a token of another
type — `prepare_token_request(url, options)`, `present_token(token, method, url,
options)` and `on_response(response, url)`. **`BearerTokenType`** carries the token
under the request's `auth_bearer`.

Everything in the folder is importable with nothing beyond the package's own
dependencies, except the assertion pair — `ClientSecretJwt` and `PrivateKeyJwt`, over
`AbstractClientAssertion` — which signs a JWT and needs joserfc, carried by the `oidc`
extra: import them from `xtr_security_http.oauth2.client_authentication.client_secret_jwt`
and `...private_key_jwt`, which name the extra when it is missing.

### OIDC

The `oidc/` folder at the package root is the **client** side of OpenID Connect — what an
application that *talks to* a provider builds its login flow from, next to `oauth2/` and a
different concern from `access_token/oidc/`, which is the resource server verifying the tokens
that arrive.

**`OidcDiscovery`** fetches and caches a provider's discovery document, over the HTTP client
and cache contracts:

```python
from xtr_security_http.oidc import OidcDiscovery

discovery = OidcDiscovery(
    http_client,
    cache,
    issuer="https://issuer.example",
    checked_endpoints=("token_endpoint", "userinfo_endpoint"),
)
```

The configuration URL defaults to the well-known path relative to the `issuer` (or the client's
`base_uri` with no issuer); the issuer must be `https` — the loopback hosts local development
serves on excepted, `is_secure_url` is the check — and the document must announce the same
issuer, a trailing slash ignored on both sides. The endpoints named in `checked_endpoints` are
weighed before anything is cached: one that would downgrade the `https` transport that carried
the document is refused, and so is a missing one; `checked_mtls_aliases` weighs the
`mtls_endpoint_aliases` entries the same way. The raw payload is cached (under `cache_key`, or
a key derived from the URL) for `cache_ttl` seconds — `None` leaves the lifetime to the pool —
and memoized per instance, so repeated reads within one authentication cost one fetch.
`get_configuration()` returns the document, `get_secure_endpoint(member)` an announced
`https` endpoint, `get_issuer()` the announced issuer (an expected one required, RFC 8414
Section 3.3), `prefetch()` sends the request without waiting for its response, and `reset()`
forgets the memo. Nothing is cached that exceeds 1 MiB.

**`OidcJwks`** is the static helper both OIDC entry points read keys through:
`from_response(response, enforce_key_usage_verification=True, clock=None)` returns the
filtered signing keys and the TTL the response's headers leave — `Cache-Control: max-age`,
or `Expires` counted from the response's `Date` or the clock, minus the response's `Age`
(RFC 9111 arithmetic), `None` when nothing is left — and `fetch_keys(http_client, jwks_uri,
item, default_ttl=3600)` lands them in a cache item, capped at 30 days. Strict (the default)
keeps only keys declared for signatures (`use: sig` or `key_ops` holding `sign`/`verify`);
lax keeps keys declaring neither; a key without a `kty`, or with a `kid` that is not a
string, is dropped either way.

**`OidcSignatureVerifier`** verifies an ID token's signature against the provider's JWKS —
discovered from the `jwks_uri` of the discovery document, cached with the header TTL
arithmetic above, refetched when a token names a `kid` the cached set lacks, throttled to
once every 60 seconds. The `alg` header is checked first against the allow-list
(`("RS256",)` by default) — **no MAC algorithm is ever accepted**, so a public key the
provider publishes can never be turned into the shared secret of an `HS256` token — and the
claims come back for `OidcIdToken.validate_claims` to confront.

**`OidcIdToken`** decodes a JWT without verifying its signature (`decode`) and validates the
claims per OIDC Core 1.0, Section 3.1.3.7 (`validate_claims(claims, expected_issuer,
expected_audience, expected_nonce=None, max_age=None)`): `iss`/`aud`/`exp`/`iat`/`sub` are
mandatory, the time claims are read against the injected clock with the allowed drift,
`azp` must name the client when present, the `nonce` must match when one was sent, and a
requested `max_age` turns `auth_time` mandatory and must not be exceeded.

**`OidcClientInterface`** / **`OidcClient`** are the protocol operations the login flow needs:
`request(endpoint, body, options)` makes a client-authenticated POST to any endpoint the
provider announces (the `client_id` added to the form body, the registration's
`ClientAuthenticationInterface` applied against the token endpoint whatever is called, no
redirect followed), `exchange_code(code, redirect_uri, code_verifier=None)` runs the
authorization-code grant, `refresh_token(refresh_token, scopes=())` the refresh grant — a
4xx `invalid_grant` raises `OidcInvalidGrantError`, the one error a caller has to tell apart —
`fetch_user_info(access_token)` presents the token to the userinfo endpoint, and
`get_client_authentication_method()` names the registration. With `certificate_options`
(`local_cert`/`local_pk`/`passphrase`) the requests go to the `mtls_endpoint_aliases` the
document announces (RFC 8705, Section 5). The access token type is the bearer one; a token
bound to a key a proof factory signs for is not asked for here.

**`OidcTokenRefresher`** renews the tokens a security token carries, in place:
`refresh_if_needed(token)` renews when the `oidc_access_token_expires_at` attribute is within
`leeway` (30 seconds by default), `refresh(token)` renews whatever the expiry and stores the
new `oidc_access_token`, `oidc_access_token_expires_at`, the rotated `oidc_refresh_token` and
the refreshed `oidc_id_token` with its `oidc_sid` — a refreshed ID token is validated against
the discovery document's issuer and the client id, and its `sub` must match the previous
token's in constant time, and nothing is stored until the whole response has passed.

**`OidcLoginAuthenticator`** (`authenticator/`) lands the whole Authorization Code Flow on
top of that machinery — the entry point, the callback and the token, one class:

```python
from xtr_security_http.authenticator import OidcLoginAuthenticator

authenticator = OidcLoginAuthenticator(
    http_utils,
    user_provider,
    oidc_client,
    discovery,
    id_token,
    "shop-api",
    success_handler,
    failure_handler,
    options={"check_path": "/oidc/callback", "scope": ("openid", "email")},
    signature_verifier=verifier,
    clock=clock,
    event_dispatcher=dispatcher,
)
```

`start()` builds the authorization redirect: a `state` and a `nonce` of the flow's own, a
PKCE code verifier (`S256` by default, `plain` on option, never off for a public client)
with its challenge, the scopes — `openid` always, first — the configured `max_age` when one
is given, and the extra `authorization_params`, after the managed-parameters guard refused
any of `response_type`/`client_id`/`redirect_uri`/`scope`/`state`/`nonce`/`code_challenge`/
`code_challenge_method`/`max_age`/`dpop_jkt` — the parameters the authenticator computes
itself, so that no configuration can weaken them. Each pending attempt lives under its own
session key (`_security.oidc_login.<firewall>.attempt.<state>`), capped at five, oldest
dropped first. `start_re_authentication(request, token)` sends `prompt=login` with the
previous ID token as `id_token_hint`, applied after the event so a listener cannot drop
them. `authenticate()` consumes the callback (a POST reads the body, anything else the
query): the `state` is matched in constant time and the attempt consumed whatever follows —
a replayed callback fails, the other attempts survive — then the RFC 9207 `iss` parameter
is checked against the announced issuer (mandatory when the provider announces
`authorization_response_iss_parameter_supported`), the provider's `error` answered, the code
exchanged with the PKCE verifier and the very `redirect_uri` the flow started on, the ID
token's signature verified before its claims are read, the claims validated against the
issuer, the client, the nonce and the `max_age`, and the user loaded from the claims the
configured `user_data_source` names (`userinfo` — its `sub` bound to the ID token's in
constant time — or `id_token`), with every claim handed to the loader as badge attributes.
`create_token()` stamps the `oidc_*` attributes the refresher renews and the back-channel
logout matches — `oidc_id_token`, `oidc_access_token`, `oidc_refresh_token`,
`oidc_access_token_expires_at` (the clock's now plus `expires_in`, when the provider sent
one), `oidc_acr`, `oidc_sid` — and the authentication proofs: the `amr` methods keyed to
`min(auth_time, now)` — a provider whose clock runs ahead never extends the recency window —
or to the login instant without an `auth_time`. A public client — one authenticating with
`none` — is refused when PKCE is off or no signature verifier was given, at use time so the
client can stay lazy. The login is interactive; a missing session is refused loudly.

**`OidcAuthorizationRequestEvent`** (`event/`) is dispatched while that redirect is being
built, before anything is stored in the session: it carries the request, the firewall and
the extra parameters, and a listener may compute them per request — `set_param`,
`remove_param`, `set_params` — with the same managed-parameters guard refusing a listener
that sets one of the flow's own.

With the `oidc` extra, the resource-server side keeps its own pieces:
**`OidcTokenHandler`** (`access_token/oidc/`) verifies a third-party issuer's tokens against
an `OidcKeySetProviderInterface` — `StaticOidcKeySetProvider(jwks)` for a fixed JWKS, or
`DiscoveryOidcKeySetProvider(http_client, cache, base_uri=... | jwks_uri=...)`, rebuilt on the
aligned discovery and the JWKS reader above: it discovers the `jwks_uri` through an
`OidcDiscovery` of its own (the issuer checked for `https` and for the issuer the document
announces, the `jwks_uri` weighed), keeps the keys in the injected cache for what the
provider's headers leave — or `jwks_cache_ttl` seconds — and refetches on a `kid` the cached
set lacks, no more than once every 60 seconds. The handler checks the signature against an
explicit **algorithm allow-list** (refusing `none` and symmetric `HS*`), the `iss` against the
trusted issuers, the `aud` against the audience, and the time claims against a clock with
leeway. **`exp` is required** — a token that never expires is refused. A key set that cannot
be fetched, discovered or read raises `OidcKeySetError`; every endpoint must be `https` —
the loopback hosts excepted — unless `allow_insecure_http` opens the development door.

**`OidcUserInfoTokenHandler`** (`access_token/oidc/`) validates a token the other way round:
it presents it to the issuer's userinfo endpoint as a bearer credential and takes the claims
the endpoint answers with as the user — the one arrangement where the issuer's own answer,
over the transport the client carries, is the whole of the validation:

```python
from xtr_security_http.access_token.oidc import OidcUserInfoTokenHandler

handler = OidcUserInfoTokenHandler(
    HttpxHttpClient().with_options(base_uri="https://issuer.example/userinfo"),
    claim="sub",
)
```

The endpoint is the client's base URI, or the one the issuer's discovery document announces
after `enable_discovery(cache, cache_key)` — which builds an `OidcDiscovery` over the
handler's own client, the document kept under `cache_key + ".document"` with no lifetime of
its own (the pool decides) and its `userinfo_endpoint` weighed before anything is cached.
`reset()` forgets the memoized document. The identifier is read from `claim` (`sub` by
default); the badge's loader is wrapped in a `FallbackUserLoader`, so the access-token
authenticator replaces it with the firewall's user provider when one is configured, and
without one the loader builds the core `OidcUser` the claims describe. Every failure becomes
an `InvalidAccessTokenError` — a missing claim raises `MissingClaimError` on the chain, a bad
signature names `InvalidSignatureError`.

**`OidcTokenGenerator`** (`access_token/oidc/`) signs the other side: an access token this
application issues, as RFC 9068 profiles one — `typ: at+jwt` in the header, the user on `sub`
(or the claim configured), the audience, the issuer, and `exp`/`nbf` from a `ttl` and a
not-before:

```python
from xtr_security_http.access_token.oidc import OidcTokenGenerator

generator = OidcTokenGenerator(
    ("RS256",),
    keyset,
    "shop-api",
    ("https://this-application.example",),
)
token = generator.generate("alice", ttl=3600)
```

The algorithm and the issuer are each either named at every call or declared as the only one;
the signing key is chosen from the key set — one whose declared use is signing and that fits
the algorithm. **`OidcTrait`** is the mixin the OIDC handlers share: `create_user(claims)`
builds the `OidcUser` the claims describe, and `check_discovered_endpoint(endpoint, key,
discovery_url)` refuses an endpoint a discovery document must not announce.

### OAuth2 scopes

A scope requirement is written as an access-control attribute. `oauth2_scope("books:read",
"books:write")` builds the string `"OAUTH2_SCOPE(books:read books:write)"`;
`parse_oauth2_scope(attribute)` reads the scopes back out, or `None` for anything not shaped like
it. **`OAuth2ScopeVoter`** grants when the token holds every asked-for scope, reading the
`oauth2_scope` attribute an authenticator copied onto it; **`InsufficientScopeAccessDeniedHandler(realm=None)`**
answers a denied scope with a `403` carrying the RFC 6750 `insufficient_scope` challenge.

### Security events

Ten events are raised around a request's authentication — `CheckPassportEvent`,
`AuthenticationTokenCreatedEvent`, `InteractiveLoginEvent`, `LoginSuccessEvent`, `LoginFailureEvent`,
`CheckRefreshedUserEvent`, `TokenDeauthenticatedEvent`, `LogoutEvent`, `SwitchUserEvent`,
`OidcAuthorizationRequestEvent`.
A subscriber listens to the event class itself (the dispatcher derives each event's name from its
class) — except `InteractiveLoginEvent` and `SwitchUserEvent`, the two events that carry a name of
their own, `SecurityEvents.INTERACTIVE_LOGIN` (`security.interactive_login`) and
`SecurityEvents.SWITCH_USER` (`security.switch_user`), because an application listens for a user's
own login or a user switch across the whole flow rather than at one authenticator.
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
| `InvalidCsrfTokenError` | `AuthenticationError` | a passport's cross-site request forgery token did not check out — the login it guards is refused |
| `ImpersonationError` | `RuntimeError` | an impersonation address was asked for and could not be built — no firewall with a switch, a forgery-asking switch without a manager, or a dedicated path configured as a route name |
| `InvalidSessionStrategyError` | `RuntimeError` | a session strategy was asked to act under a name that is none of its own; carries `strategy` |
| `LogoutError` | `RuntimeError` | a logout request failed its cross-site request forgery proof |
| `MissingSessionError` | `RuntimeError` | a session strategy was asked to move a request whose security state carries no session |
| `UnknownFirewallError` | `LookupError` | a firewall was asked for by a name none is registered under; carries `name` and `configured` |

## Layout

```
xtr_security_http/
├── firewall_map.py             FirewallMap, matched or fetched by name
├── firewall_context_interface.py  one firewall's runtime pieces
├── firewall/                   Firewall (the subscriber), AccessListener, ChannelListener,
│                              ContextListener, ExceptionListener, LogoutListener,
│                              SwitchUserListener, RefreshUserResult,
│                              FirewallListenerInterface, AbstractListener
├── authentication/             AuthenticatorManager, handlers, ExposeSecurityLevel
├── authenticator/              AuthenticatorInterface, AccessTokenAuthenticator,
│                              OidcLoginAuthenticator, the pre-authenticated trio,
│                              passport/, token/
├── access_token/               extractors, handler interface, oauth2/ (Oauth2TokenHandler),
│                              oidc/ (OidcTokenHandler)
├── oidc/                       DiscoveryOidcKeySetProvider
├── oauth2/                     the client side: JwsAlgorithms, BearerTokenType, the
│                              client-authentication methods (the assertion pair behind
│                              the oidc extra)
├── access_map.py               the ordered access-control rules
├── request_matcher/            the callable escape hatch (the rest come from xtr-http-foundation)
├── authorization/              OAuth2ScopeVoter, oauth2_scope, the scope-denied handler
├── decorator/                  IsGranted, CurrentUser, CurrentToken, IsCsrfTokenValid,
│                              FirewallListenerOrder
├── resolver/                   the enforcement services behind the markers
├── entry_point/                AuthenticationEntryPointInterface
├── event/                      the firewall events around a login, a logout and a switch
├── event_listener/             the listeners the bundle registers (incl. the timing guard)
│                              and the logout listeners answering LogoutEvent
├── impersonate/                ImpersonateUrlGenerator, ImpersonationForm, SwitchUserConfig,
│                              SwitchUserConfigLookupInterface — the switch addresses
├── rate_limiter/               DefaultLoginRateLimiter — the limits a login's failed attempts
│                              count under, keyed by the address and the account
├── login_link/                 the signed links a login arrives by: details, handler,
│                              handler interface
├── logout/                     LogoutUrlGenerator, LogoutForm — the logout addresses
├── remember_me/                the handlers, details, staged cookie and response pass of a
│                              login the user asked to outlive its session
├── session/                    what a login does to the session it reattached
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
