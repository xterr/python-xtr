<div align="center">

# xtr-security

**The security bundle for xtr applications: the family facade and the container wiring that configures it.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

The security family is four libraries — [xtr-security-core](../xtr-security-core),
[xtr-security-http](../xtr-security-http), [xtr-security-csrf](../xtr-security-csrf) and
[xtr-password-hasher](../xtr-password-hasher) — each usable on its own. Wiring them together
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
uv add xtr-security                    # the bundle, wiring core, http, csrf and the password hasher
uv add xtr-console                     # beside it: debug:firewall and security:hash-password
uv add "xtr-security-http[oidc]"       # + verifying third-party OIDC issuers' tokens
```

Requires Python 3.11+. The core, http-edge and password-hasher libraries come with the package;
[xtr-console](../xtr-console), installed beside it, adds the commands. The forgery-token library
comes with the package too — the bundle builds its manager itself where a firewall asks for a
token — and so does the [rate limiter](../xtr-rate-limiter), whose factories a throttled
firewall's attempts count under. The `oidc` extra of
[xtr-security-http](../xtr-security-http) adds joserfc and httpx; the bundle registers the OIDC
token handler, the userinfo handler and the OIDC login factories only when that extra is
installed. Self-issued JSON Web Tokens are a
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
| `http_port` | `80` | The port plain `http` answers on, spelled out in a channel redirect when it is not the default |
| `https_port` | `443` | The port `https` answers on, spelled out in a channel redirect when it is not the default |
| `expose_security_errors` | `NONE` | How much of an authentication failure reaches the client |
| `trace_votes` | `None` | Announce every vote as an event and log every decision; `None` follows `kernel.debug` |
| `authenticator_factories` | built-ins | The factories that build firewalls' authenticators |
| `token_handler_factories` | built-ins | The factories that build access-token handlers |
| `user_provider_factories` | built-ins | The factories that build user providers |

The built-ins the zero-config path carries: **eight** authenticator factories — access token,
form login, HTTP basic, JSON login, login link, remember me, remote user and X509 — joined by a
ninth, the OIDC login, only when the `oidc` extra is installed; **two** token-handler factories —
a service handler and the OAuth2 introspection one — joined by the OIDC and userinfo ones under
the same extra; and **three** user-provider factories — in-memory, chain and service. Nothing
else registers unconfigured: no firewall, no rule, no voter beyond the built-ins.

### Firewalls

`FirewallConfig` claims a slice of the request space and says how it authenticates:

| Field | Default | What it is |
|---|---|---|
| `pattern` | `None` | A regular expression matched against the request path |
| `host` | `None` | A regular expression matched against the request host |
| `methods` | `()` | The HTTP methods claimed; every method when empty |
| `request_matcher` | `None` | A callable `(ServerRequestInterface) -> bool`, tried last |
| `security` | `True` | `False` lets every request the firewall claims through untouched |
| `stateless` | `True` | Whether the firewall keeps no session. A stateful firewall (`stateless=False`) restores the token its session carries on every request, through the `SessionStorageInterface` service the application registers; with none registered the build fails naming it |
| `context_key` | `None` | The name the firewall's context is stored under in the session — the part after `_security.` — or `None` for the firewall's own name |
| `session_strategy` | `migrate` | What a successful login does to the session it reattached: `migrate` rotates its ID keeping its attributes, `invalidate` empties it, `none` leaves it alone. Meaningful on a stateful firewall only |
| `provider` | `None` | The user provider the firewall loads users from; with none here and none configured at all, an authenticator that needs one gets a `MissingUserProvider` that fails, naming the firewall, when first used — and with none here but others configured, one that needs one fails the build, naming the firewall |
| `user_checker` | `None` | A user-checker service type, or the default in-memory checker |
| `entry_point` | `None` | The authenticator whose challenge answers an unauthenticated request |
| `access_denied_handler` | `None` | A handler for a denied, fully-authenticated caller |
| `scope_denied_handler` | `None` | A handler service type answering a caller whose token lacks a scope a rule asks for — wrapped by the bundle's `WWW-Authenticate` answer |
| `authenticators` | `()` | The authenticator configurations the firewall runs |
| `required_badges` | `()` | Badge types every passport must carry |
| `csrf_route_markers` | `False` | Whether the firewall's routes prove themselves with `IsCsrfTokenValid` markers — wiring the forgery-token manager for them even when no login or logout asks; the tokens travel in the session, so a stateless firewall declaring them fails the build |
| `logout` | `None` | The logout the firewall's requests can ask for — see below |
| `switch_user` | `None` | The switch-user block the firewall's callers switch by — see below |
| `login_throttling` | `None` | How the firewall's logins are counted and refused — see below |
| `re_authentication_entry_point` | `None` | A service type starting a fresh proof for an already-authenticated caller — handed to the firewall's exception listener the way the denial handlers are, so a recency refusal is answered with a fresh proof instead of the plain `403` |
| `listeners` | `()` | The qualifiers of the firewall's own listener chain, each naming a listener aliased under `FirewallListenerInterface`; the sorting pass orders them with the steps the bundle parks |

The matchers those fields build come from [xtr-http-foundation](../xtr-http-foundation), and each
of them — `request_matcher`'s callable included — reads the request as a message.
`pattern` matches the path below the application's mount, with per-cent escapes undone; `host` is
matched without regard to case.

The firewalls run as the firewall — a subscriber `SecurityBundle` registers over the kernel
lifecycle's events, before routing — so the routes carry no firewall dependency of their own:
each request runs the first firewall whose matcher claims it, authenticated once, and a route
documents its security with the framework's own params.

### Stateful firewalls

A stateful firewall (`stateless=False`) carries a context step at the head of its chain — the
`ContextListener` restoring the token its session holds, reloading the user it carries through
the firewall's provider, and writing the token back on the response — registered by the bundle
under `<firewall>#context_listener` and parked ahead of the authentication step. The session
itself is the application's: the `SessionStorageInterface` service it registered (an in-memory
one for a single process, a cache-pool one for a shared backend) is what the listener builds
the session from, and a stateful firewall with none registered fails the build naming the
service — the bundle never builds one silently, and a firewall the application asked to be
stateful cannot quietly run as a stateless one.

A successful login hands the session to the firewall's `session_strategy` — `migrate` by
default, rotating the session's ID so a fixation stops answering for the account the login
named — through a `SessionStrategyListener` on the firewall's own dispatcher.

The response side is wired with the request side: the context step's response half stores
the token the request authenticated back into the session it reattached, and a
`SaveSessionListener` on the kernel's response event writes that session through the
storage and stages the cookie that carries its ID — a fresh session, or one a login
rotated. The save runs below every other response listener, so the token is in the
session before the session is written, and a storage that fails fails the request
loudly rather than losing the session quietly; the finish event saves what a request
that failed without producing a response still wrote. The listener is registered while
any stateful firewall is configured and carries the same remove-if-missing marker over
the application's session storage as the context step it serves.

### The authenticator family

A firewall's `authenticators` tuple lists what proves its callers, each entry matched to a
registered factory by the factory's `config_type`. The built-ins:

| Configuration | Key | Entry point | Proves the caller by | Asks for |
|---|---|---|---|---|
| `AccessTokenConfig` | `access_token` | fallback — answers alone when no real challenge runs | a bearer token, validated by its `token_handler` | nothing: the handler builds the user; stateless |
| `HttpBasicConfig` | `http_basic` | real — the browser's credential prompt | the `Authorization: Basic` header | a user provider |
| `FormLoginConfig` | `form_login` | real — the redirect to the login page | a submitted form | a user provider, a stateful firewall |
| `JsonLoginConfig` | `json_login` | none | a JSON document | a user provider |
| `OidcLoginConfig` | `oidc_login` | real — the redirect to the provider | an authorization-code flow | a user provider, a stateful firewall, the `oidc` extra |
| `RememberMeConfig` | `remember_me` | none | the cookie a login left | a user provider; the persistent handler also a `TokenProviderInterface` service |
| `LoginLinkConfig` | `login_link` | none | a signed link it mints | a user provider |
| `RemoteUserConfig` | `remote_user` | none | the account the server in front named | a user provider |
| `X509Config` | `x509` | none | the client's certificate | a user provider |

The factories order the authenticators they build by priority: the access-token and the
pre-authenticated ones at `100`, the interactive logins at `0`, the remember-me at `-100` —
a request presenting several proofs is read by the freshest kind first. The entry point
resolves by kind: a configured `entry_point` name wins (naming one of the firewall's
authenticators, or the build fails naming it); with none configured, a single authenticator
answers regardless of kind, the one `real` kind answers when there is exactly one, a
`fallback` answers alone when nothing real runs — and a firewall with several
authenticators, an access rule that needs authentication and no resolvable entry point
fails the build, naming `entry_point`. A third-party factory that does not answer
`entry_point_kind` is read as never challenging, so it never takes the resolution over.

### HTTP basic

An `HttpBasicConfig` builds the HTTP basic login: no page, no session — the browser's own
`Authorization: Basic` header is the proof, and the `401` carrying
`WWW-Authenticate: Basic realm="…"` is both a failed attempt's answer and the firewall's
entry point. The `realm` defaults to `Secured` and must not be empty.

### OIDC login

An `OidcLoginConfig` builds the authorization-code login — behind the `oidc` extra, with a
user provider, on a firewall that reattaches a session: the login parks its pending
attempts in one, so on a stateless firewall it fails at use with `MissingSessionError`,
not at build. The provider is discovered from `issuer`, the
client named by `client_id` authenticates at the token endpoint by
`token_endpoint_auth_method` — one of `none`, `client_secret_basic` (the default),
`client_secret_post`, `client_secret_jwt`, `private_key_jwt`, `tls_client_auth`,
`self_signed_tls_client_auth`. A secret-bearing method needs `client_secret` and a method
that sends none refuses one; `private_key_jwt` signs its assertion with
`client_authentication_keyset`; the TLS pair presents the certificate carried in
`certificate_options`. PKCE is on, `S256` by default; the user is read from the `userinfo`
endpoint — its `sub` bound to the ID token's — or from the `id_token` claims, by
`user_data_source`; `signature_verifier_algorithms` verifies the ID token's signature
against the provider's keys, and `None` reads its claims without verifying. The callback
answers on `check_path` (`/oidc/callback` by default), `scope` adds to the always-asked
`openid`, `max_age` bounds how old an authentication may be, and `authorization_params`
carries extra parameters — the ones the flow manages, `response_type` through `dpop_jkt`,
are guarded so no configuration can set them.

Three sub-blocks ride on the login. `token_generator` (`OidcTokenGeneratorConfig`) mints
this application's own tokens through the `security:oidc:generate-token` command — see
below. `backchannel_logout` and `end_session` wire the provider-pushed logout, documented
under [The OIDC back channel](#the-oidc-back-channel). And a token-refresh listener joins
the firewall's chain, ordered after the context step, renewing the access token of a
login whose expiry falls within the refresher's leeway — a refresh the provider no longer
honors clears the token, so the request goes on anonymous.

### Remember me

A `RememberMeConfig` builds the remember-me login: a request presenting the cookie a
previous login left is logged back in, lazily — the factory's priority `-100` puts it
behind the interactive authenticators, so a fresher proof always wins. `handler` picks how
the cookie is held: `signature` signs the value over the user's covered properties, so a
changed password retires every cookie; `persistent` keeps a series per cookie through the
application's `TokenProviderInterface` service, named by qualifier in `token_provider` —
refused by name at wiring when the persistent handler is asked for without one. The cookie's
shape — `name` (`REMEMBERME`), `lifetime` (a year), `path`, `domain`, `secure`, `httponly`,
`samesite` — and the ask — `always_remember_me`, or the request's `remember_me_parameter`
(`_remember_me`) — are the configuration's own fields; `signature_properties` names the
user properties whose digest a persisted value carries (the password by default). The
`secret` the signature rides on is a configuration field, read from the environment the
way [Secrets](#secrets) shows — never generated. Two subscribers on the firewall's
dispatcher ask a successful login whether it asked to be
remembered (at `-32`) and set or clear the cookie (at `-64`); one response listener on the
main dispatcher moves the staged cookie onto the response. The handler itself is a service
— `SignatureRememberMeHandler` or `PersistentRememberMeHandler`, qualified
`<firewall>#remember_me_handler` — addressed with `Target` wherever a cookie is minted or
cleared by hand.

### Login links

A `LoginLinkConfig` builds the login-link authenticator: a link minted through the
firewall's own handler service signs its user in when followed. The handler —
`LoginLinkHandlerInterface`, qualified `<firewall>#login_link_handler` — is what an
application mints through: `path` is the literal path every minted link leads to and
`check_path` the literal path a followed link arrives at, both required; `lifetime`
counts 600 seconds by default; `check_post_only` demands a POST of the follow;
`signature_properties` (the password by default) retires every link of a user when any of
them changes. The `secret` the hash is signed with is a configuration field, read from the
environment the way [Secrets](#secrets) shows — never generated. The success and failure
handlers follow the form login's pattern — the default pair, or the application's own
named by service type.

### Login throttling

A firewall's `login_throttling` block counts its login attempts: `global_limit` per
`global_interval` from one client address, `local_limit` per `local_interval` from one
account at one address — five per fifteen minutes each by default — the global count
surviving any one account's success, so one client may not farm a whole directory. The
counts live in the application's `StorageInterface` service (from
[xtr-rate-limiter](../xtr-rate-limiter)), the same storage every other limiter of the
application counts in, and the keys are HMAC prefixes over the block's `secret`, so a
shared store keeps no readable account or address — the `secret` a configuration field,
read from the environment the way [Secrets](#secrets) shows, never generated. The listener
runs on the firewall's dispatcher at `2080`, ahead of the provider's `2048` — a request
already over the limit is refused before any user is loaded or any password verified.

### Switch user

A firewall's `switch_user` block parks the switch step on its chain, ordered after the
manager's own through the step's `FirewallListenerOrder` declaration: a caller holding the
block's `role` (`ROLE_ALLOWED_TO_SWITCH` by default, weighed against the target user as the
subject) becomes another user by carrying `parameter` (`_switch_user`) — on any page the
firewall claims, or on the dedicated `path` — and steps back out with the same parameter
carrying `_exit`. `enable_csrf` asks for a forgery token under `csrf_parameter` and
`csrf_token_id` (`switch_user`), refused on a stateless firewall, which has no session to
keep the tokens in. One scoped `ImpersonateUrlGenerator` service renders the addresses a
page switches by — the impersonation and exit paths, URLs and forms — reading the
request's firewall's block through a lookup built from the firewall map.

The bundle hands the step the firewall's own dispatcher, so the `SwitchUserEvent` it
announces — before a switch settles, and before an exit restores the original token —
reaches the listeners of `firewall_dispatcher_name(firewall)` beside the firewall's other
events.

### Pre-authenticated

`RemoteUserConfig` and `X509Config` build the pre-authenticated logins, tagged apart by
their `type` field: one reads the account the server in front wrote under `user_key`
(`REMOTE_USER` by default), the other the certificate the server verified — the email
under `user_key` (`SSL_CLIENT_S_DN_Email`), or the configured identifier out of the
distinguished name under `credentials_key` when there is no email. Both need a user
provider and both run at priority `100`; neither answers a challenge, so a request they
cannot read goes on anonymous to the next authenticator.

### Form login

A `FormLoginConfig` builds the form login: the form rendered at `login_path`, submitted to
`check_path` — a POST there, its fields read by the names the form gives them
(`username_parameter`, `password_parameter`), a form content type demanded when `form_only` is
set. A failed login stores its error on the session and redirects back to the page; a successful
one is answered by the target ladder — the default pair of handlers, or the application's own
pair, named by service type in `success_handler` and `failure_handler`, answered through the
bundle's wrappers. The redirect to the login page is a real entry point: an unauthenticated
request is sent there to prove itself.

The login is stateful — its errors travel in the session, its success rotates it — so it is
refused on a stateless firewall, where it could only ever answer the one request that submitted
it. It needs the firewall's user provider.

### JSON login

A `JsonLoginConfig` builds the JSON login: the request's parsed body read by the dotted paths
`username_path` and `password_path`, the path it is submitted to named by `check_path` — or
`None` for every request carrying a JSON body. The login is stateless and never challenges: a
failed login is answered with a plain `401` carrying the error's message, or the application's
own handlers when `success_handler` and `failure_handler` name them. A firewall whose only login
is this one resolves its entry point elsewhere.

### Cross-site request forgery

The forgery machinery is opt-in: it is wired when a firewall's configuration asks for a token —
a form login with `enable_csrf`, a logout with `enable_csrf` or `clear_csrf_tokens`, a
`switch_user` block with `enable_csrf` — and nothing
registers without an ask. A firewall whose routes prove themselves with `IsCsrfTokenValid`
markers asks the same way, with `csrf_route_markers` — the marker's checker answers through
the manager, so the declaration wires it; the tokens travel in the session the request
reattached, so a stateless firewall declaring them fails the build. The bundle then builds
the csrf package's manager over the session the
request reattached, as the application's one `CsrfTokenManagerInterface` service: the route
marker's checker survives on its arrival, and the passport check settles the badge a form login
mints, ahead of the credential check, at the priority the landed listener declares. The tokens
themselves travel in the session — the storage reads it anew on every call, so the machinery
works whatever moment its services are built in — and a migration empties them with the session
it rotates.

### Logout

A firewall with a `LogoutConfig` carries a logout step on its context — the request asking for
the configured `path` is logged out, its token cleared — and the logout event it announces is
answered on the firewall's own dispatcher by the listeners the configuration turns on: the
default redirect to `target_path`, the `Clear-Site-Data` header, the configured cookies
cleared, and the session invalidated on a stateful firewall. One `LogoutUrlGenerator` service
carries every firewall's registration, so whatever renders a page asks for a logout's address
by the firewall's name — or with none, resolved over the current request's token, or over
the firewall the request runs under: the bundle names the matched firewall on the
generator per request, so an anonymous page under a firewall with a logout renders that
logout's address too. The generator is scoped to the request, so what one request named
never answers for the next.

The cross-site request forgery checks a logout can ask for are wired with the machinery above:
`enable_csrf` has the step prove the request with the manager before it logs out, and
`clear_csrf_tokens` drops every token the request's session minted on the logout event. Both
need the session the tokens are stored in, so a stateless firewall asking for either fails the
build saying so.

### The OIDC back channel

An OIDC login can carry a `backchannel_logout` and an `end_session` block. The end-session
listener joins the firewall's own logout listeners, redirecting the application's logout to
the provider's end-session endpoint. The back-channel logout records the sessions the
provider says have ended, into the `CacheItemPoolInterface` service the application
registered — a pool shared by every server, never one the bundle builds — and refuses the
logins they name through a listener on the refreshed-user check.

The route the provider pushes its logout tokens to is the application's to map: the bundle
registers an `OidcBackChannelLogoutHandler` service, qualified by the firewall's name, and
the application serves it at the path it configured as the block's `route`:

```python
from typing import Annotated
from fastapi import Form
from xtr_dependency_injection import Target
from xtr_http_kernel.bridge import Response

from xtr_security import OidcBackChannelLogoutHandler


@app.post("/logout/backchannel")
async def backchannel_logout(
    logout_token: Annotated[str | None, Form()] = None,
    answer: Annotated[OidcBackChannelLogoutHandler, Target("main")] = None,
) -> Response:
    return await answer(logout_token)
```

The endpoint is public and unauthenticated by design — the request comes from the provider,
carrying nothing of the browser that logged in — and a refusal answers the bare `400` with
no detail: the reason is the verifier's to name in the log, not the caller's to read.

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
| `Oauth2TokenHandlerConfig(introspection_base_uri, …)` | `oauth2` | A token by introspecting it with its authorization server (RFC 7662) |
| `OidcTokenHandlerConfig(issuers, audience, …)` | `oidc` | A third-party OIDC issuer's tokens (needs the `oidc` extra) |
| `OidcUserInfoTokenHandlerConfig(userinfo_base_uri, …)` | `oidc_user_info` | A token by presenting it to the issuer's userinfo endpoint (needs the `oidc` extra) |

`OidcTokenHandlerConfig` takes exactly one key source — `keyset` (a JWKS document), `discovery_uri`
(an issuer base URI the `jwks_uri` is discovered from) or `jwks_uri` — plus the `issuers` and
`audience` a valid token must carry; `algorithms` default to `("RS256",)`, `claim` to `"sub"`.

`Oauth2TokenHandlerConfig` reaches the introspection endpoint through a scoped client over
`introspection_base_uri` with this resource server's `credentials`, or through the `client`
service the application registered; `audiences` and `issuer` are checked only when given, a
`cache` service keeps active responses for `cache_ttl` seconds, and
`signed_response_algorithms` asks for the response as a signed JWT — verified against
`signed_response_keyset` or against the keys the issuer's metadata publishes, read through
the `signed_response_discovery_cache` service (which needs `issuer`). A signed response
needs the `oidc` extra, as the handler's own section in
[xtr-security-http](../xtr-security-http) notes. `OidcUserInfoTokenHandlerConfig` reads the
endpoint from `userinfo_base_uri` — or from the issuer's discovery document through the
`discovery_cache` service, kept under `discovery_cache_key` — and the identifier from
`claim` (`sub` by default).

### Access control

`AccessControlConfig` is a request pattern and the one attribute a matching request must hold —
a role, `"IS_AUTHENTICATED"`, `"PUBLIC_ACCESS"`, or an `OAUTH2_SCOPE(...)` string. Rules are
tried in order, so a narrow `^/api/admin` rule comes before the broad `^/api`.
`path` matches below the application's mount with per-cent escapes undone, `host` without regard
to case; an `ips` entry is an address or a network, written in CIDR or netmask form.

A rule may also name a `channel` — `"https"` or `"http"` — the request must arrive over; a
matching request arriving over the wrong one is not decided at all but redirected, by the
channel step below.

### The channel

A firewall whose access rules carry a channel parks the channel step first on its chain —
ahead of the context step and the manager's own, so nothing a request carries is restored,
authenticated or decided before it arrives the way the rule demands. The step answers a
request arriving over the wrong scheme with a `301` to the same request over the demanded
one: the host, path and query kept, the target scheme's port spelled out from the
configuration's `http_port`/`https_port` when it is not the scheme's default. The scheme a
request is read by is its URI's own — there is no trusted-proxy machinery to weigh a
forwarded header — so an application behind a proxy that terminates the encryption reads
plain `http` here; a rule with no channel parks no step.

### Secrets

Three configurations sign or derive with a secret: the remember-me cookie (`secret`), the
login link (`secret`) and the login throttling (`secret`). Each is a plain configuration
field, so the application's own `configure` reads it from the environment the way every
other setting of the application is read:

```python
from xtr_dependency_injection import configure, env
from xtr_security.bundle import FirewallConfig, FormLoginConfig, RememberMeConfig, SecurityConfig


@configure
def security() -> SecurityConfig:
    return SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                stateless=False,
                authenticators=(
                    FormLoginConfig(login_path="/login"),
                    RememberMeConfig(secret=env("REMEMBER_ME_SECRET")),
                ),
            ),
        },
    )
```

The bundle never mints one: it builds and boots without any of them — the console still
runs, so a secret can be generated or inspected — and the service that needs one fails the
first time it is asked for, naming the setting: the login-link handler refusing
`secret` on the login-link configuration, the throttling listener refusing `secret` on the
login-throttling configuration, the remember-me handler the same on the remember-me
configuration. An empty value reads as no secret at all.

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
  `debug:firewall` and `security:hash-password` — and `security:oidc:generate-token` when a
  firewall's OIDC login mints.
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
- **Environment** — nothing the recipe writes; an application reads its own secrets through
  `env(...)` in its configuration — the remember-me, login-link and throttling `secret`
  fields, as [Secrets](#secrets) shows.
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
context carries the ordered chain — with the firewall's own exception listener, built per
firewall from its name, its entry point and its handlers, and, while the firewall configures
none, no logout listener — so `await firewall_map.get_listeners(message)` answers the matched
firewall's `(chain, exception_listener, logout_listener)`. The exception listener turns a
security error into a response on the http-kernel lifecycle, answering a request's failure
the way the firewall that ran it would; a request no firewall matched is the kernel's to
answer. Its zero-config path builds and boots with no configuration and touches no I/O
until a request arrives.

Each firewall dispatches its security events — `CheckPassportEvent`,
`AuthenticationTokenCreatedEvent`, `AuthenticationSuccessEvent`, `InteractiveLoginEvent`,
`LoginSuccessEvent`, `LoginFailureEvent`, `CheckRefreshedUserEvent`,
`TokenDeauthenticatedEvent`, `SwitchUserEvent`, `LogoutEvent`,
`OidcAuthorizationRequestEvent` — on a dispatcher of its own, named by
`firewall_dispatcher_name(firewall)`.
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
with the configured factory. A firewall whose OIDC login carries a `token_generator` block
adds a third: `security:oidc:generate-token <user-identifier>` mints a token through that
firewall's generator — `--firewall` naming which when several mint, `--algorithm` and
`--issuer` the choice when several are declared, `--ttl` and `--not-before` the token's
lifetime and start — printed bare, ready to be presented. The command is registered only
under both gates: a console active, and at least one firewall minting.

## Errors

Everything the family raises derives from `SecurityError` (from
[xtr-security-core](../xtr-security-core)); this package adds one.

| Error | Raised when |
|---|---|
| `InvalidConfigurationError` | A security configuration the bundle cannot turn into services — an unknown provider, a secured firewall with no authenticator, an authenticator with no factory, an entry point that resolves to nothing or names no authenticator of the firewall, a stateful firewall with no `SessionStorageInterface` registered, a form login or declared route markers on a stateless firewall, a back-channel logout on a stateless firewall, a switch asking for a forgery proof on a stateless firewall; also a `ValueError` |

## Layout

```
xtr_security/
├── security.py                the Security facade
├── firewall_config.py         FirewallConfig, the firewall an application writes
├── logout_config.py           LogoutConfig, the logout a firewall's requests ask for
├── login_throttling_config.py LoginThrottlingConfig, the counting a firewall's logins are refused by
├── switch_user_config.py      SwitchUserConfig, the switch a firewall's callers ask for
├── oidc_back_channel_logout_handler.py  answers the route a provider pushes logout tokens to
├── exception/                 InvalidConfigurationError
├── command/                   debug:firewall
├── factory/                   authenticator factory interface + the built-in factories,
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
    ├── refuse_stateful_firewalls_without_session_storage_pass.py  names the missing storage
    ├── register_per_call_listeners_pass.py  parks the request and wires the per-call listeners
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
