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
| `http_port` | `80` | The port plain `http` answers on, spelled out in a channel redirect when it is not the default |
| `https_port` | `443` | The port `https` answers on, spelled out in a channel redirect when it is not the default |
| `expose_security_errors` | `ExposeSecurityLevel.NONE` | How much of an authentication failure reaches the client |
| `trace_votes` | `None` | Announce every vote as an event and log every decision; `None` follows the kernel's debug flag |
| `authenticator_factories` | built-ins | The factories that build firewalls' authenticators |
| `token_handler_factories` | built-ins | The factories that build access-token handlers |
| `user_provider_factories` | built-ins | The factories that build user providers |

The built-ins the zero-config path carries: **eight** authenticator factories — access token,
form login, HTTP basic, JSON login, login link, remember me, remote user and X509 — joined by a
ninth, the OIDC login, only when the `oidc` extra of `xtr-security-http` is installed; **two**
token-handler factories — a service handler and the OAuth2 introspection one — joined by the
OIDC and userinfo ones under the same extra; and **three** user-provider factories — in-memory,
chain and service. Nothing else registers unconfigured: no firewall, no rule, no voter beyond
the built-ins.

A firewall naming a `provider` that is not declared fails the build with
`InvalidConfigurationError`, as the configuration is written.

## `FirewallConfig`

| Field | Default | What it is |
| --- | --- | --- |
| `pattern` | `None` | A regular expression matched against the request path |
| `host` | `None` | A regular expression matched against the request host |
| `methods` | `()` | The HTTP methods claimed; every method when empty |
| `request_matcher` | `None` | A callable `(ServerRequestInterface) -> bool`, tried last |
| `security` | `True` | `False` lets every request the firewall claims through untouched |
| `stateless` | `True` | `False` keeps a session: the token it carries is restored on every request, through the `SessionStorageInterface` service the application registers; with none registered the build fails naming it |
| `context_key` | `None` | The name the firewall's context is stored under in the session — the part after `_security.` — or `None` for the firewall's own name |
| `session_strategy` | `"migrate"` | What a successful login does to the session it reattached: `migrate` rotates its ID keeping its attributes, `invalidate` empties it, `none` leaves it alone. Meaningful on a stateful firewall only |
| `provider` | `None` | The name of the user provider the firewall loads users from; with none here and none configured, an authenticator needing one gets a `MissingUserProvider` that fails, naming the firewall, when first used |
| `user_checker` | `None` | A user-checker service type, or the default in-memory checker |
| `entry_point` | `None` | The authenticator whose challenge answers an unauthenticated request |
| `access_denied_handler` | `None` | A handler service type for a denied, fully-authenticated caller |
| `scope_denied_handler` | `None` | A handler service type answering a caller whose token lacks a scope a rule asks for — wrapped by the bundle's `WWW-Authenticate` answer |
| `authenticators` | `()` | The authenticator configurations the firewall runs |
| `required_badges` | `()` | Badge types every passport must carry |
| `csrf_route_markers` | `False` | The firewall's routes prove themselves with `IsCsrfTokenValid` markers; wires the forgery-token manager for them — stateful only |
| `logout` | `None` | `LogoutConfig` — the logout the firewall's requests can ask for |
| `switch_user` | `None` | `SwitchUserConfig` — the switch the firewall's callers switch by |
| `login_throttling` | `None` | `LoginThrottlingConfig` — how the firewall's logins are counted and refused |
| `re_authentication_entry_point` | `None` | A `ReAuthenticationEntryPointInterface` service type starting a fresh proof for an already-authenticated caller — handed to the firewall's exception listener the way the denial handlers are, so a recency refusal is answered with a fresh proof instead of the plain `403` |
| `listeners` | `()` | The qualifiers of the firewall's own listener chain, each naming a listener aliased under `FirewallListenerInterface`; the sorting pass orders them with the steps the bundle parks |

A secured firewall with no authenticators is refused. The matchers those fields build come from
`xtr-http-foundation` and read the request as a message: `pattern` matches the path below the
application's mount, with per-cent escapes undone, and `host` is matched without regard to case.
A firewall with no `pattern`, `host`, `methods` or `request_matcher` claims every request, so
register it last.

## Stateful firewalls

A stateful firewall (`stateless=False`) carries a context step at the head of its chain — the
`ContextListener` restoring the token its session holds, reloading the user it carries through
the firewall's provider, and writing the token back on the response. The session itself is the
application's: register one service implementing `SessionStorageInterface` (from
`xtr_http_foundation`) and every stateful firewall builds its sessions from it.

```python
from xtr_dependency_injection import as_service
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface


@as_service
def session_storage() -> SessionStorageInterface:
    return MemorySessionStorage()  # one process; a cache-pool storage for a shared backend
```

With none registered the build fails naming the service — the bundle never builds one silently,
and a firewall the application asked to be stateful cannot quietly run as a stateless one.

A successful login hands the session to the firewall's `session_strategy` — `migrate` by
default, rotating the session's ID so a fixation stops answering for the account the login
named. On the response side a `SaveSessionListener` writes the session through the storage and
stages the cookie that carries its ID — a fresh session, or one a login rotated. The save runs
below every other response listener, so the token is in the session before the session is
written, and a storage that fails fails the request loudly rather than losing the session
quietly.

## The authenticator family

A firewall's `authenticators` tuple lists what proves its callers, each entry matched to a
registered factory by the factory's `config_type`. The built authenticators run ordered by the
factories' priorities — a request presenting several proofs is read by the freshest kind first.

| Configuration | Key | Priority | Entry point | Proves the caller by | Asks for |
| --- | --- | --- | --- | --- | --- |
| `AccessTokenConfig` | `access_token` | `100` | `fallback` | a bearer token, validated by its `token_handler` | nothing: the handler builds the user |
| `RemoteUserConfig` | `remote_user` | `100` | `none` | the account the server in front named | a user provider |
| `X509Config` | `x509` | `100` | `none` | the client's certificate | a user provider |
| `FormLoginConfig` | `form_login` | `0` | `real` | a submitted form | a user provider, a stateful firewall |
| `HttpBasicConfig` | `http_basic` | `0` | `real` | the `Authorization: Basic` header | a user provider |
| `JsonLoginConfig` | `json_login` | `0` | `none` | a JSON document | a user provider |
| `LoginLinkConfig` | `login_link` | `0` | `none` | a signed link it mints | a user provider |
| `OidcLoginConfig` | `oidc_login` | `0` | `real` | an authorization-code flow | a user provider, a stateful firewall, the `oidc` extra |
| `RememberMeConfig` | `remember_me` | `-100` | `none` | the cookie a login left | a user provider; the persistent handler also a `TokenProviderInterface` service |

The entry point resolves by kind: a configured `entry_point` name wins (naming one of the
firewall's authenticators, or the build fails naming it); with none configured, a single
authenticator answers regardless of kind, the one `real` kind answers when there is exactly
one, and a `fallback` answers alone when nothing real runs. A firewall with several
authenticators, an access rule that needs authentication and no resolvable entry point fails
the build, naming `entry_point`.

### HTTP basic

`HttpBasicConfig(realm="Secured")` — no page, no session: the browser's own
`Authorization: Basic` header is the proof, and the `401` carrying
`WWW-Authenticate: Basic realm="…"` is both a failed attempt's answer and the firewall's entry
point. The realm must not be empty.

### Pre-authenticated

`RemoteUserConfig(user_key="REMOTE_USER")` reads the account the server in front wrote under
`user_key`; `X509Config(user_key="SSL_CLIENT_S_DN_Email",
credentials_key="SSL_CLIENT_S_DN", credential_user_identifier="emailAddress")` reads the
certificate the server verified — the email under `user_key`, or the configured identifier
out of the distinguished name under `credentials_key` when there is no email. Neither
challenges, so a request they cannot read goes on anonymous to the next authenticator.

### Form and JSON logins

`FormLoginConfig(login_path, check_path="/login_check", username_parameter="_username",
password_parameter="_password", post_only=True, form_only=False, enable_csrf=False,
csrf_parameter="_csrf_token", csrf_token_id="authenticate", success_handler=None,
failure_handler=None)` builds the form login — stateful only, needing the firewall's user
provider, its redirect to the login page a real entry point. The handlers are the bundle's
default pair, or the application's own services named by type and answered through its wrappers.

`JsonLoginConfig(check_path=None, username_path="username", password_path="password",
success_handler=None, failure_handler=None)` builds the stateless JSON login, which never
challenges: a firewall whose only login is it resolves its entry point elsewhere.

### OIDC login

`OidcLoginConfig(issuer, client_id, client_secret=None, …)` builds the authorization-code
login — behind the `oidc` extra, with a user provider, on a firewall that reattaches a
session: the login parks its pending attempts in one, so on a stateless firewall it fails at
use with `MissingSessionError` (from `xtr_security_http.exception`), not at build. The provider
is discovered from `issuer`; the client authenticates at the token endpoint by
`token_endpoint_auth_method` — `none`, `client_secret_basic` (the default),
`client_secret_post`, `client_secret_jwt`, `private_key_jwt`, `tls_client_auth` or
`self_signed_tls_client_auth`, a secret-bearing method needing `client_secret` and a method
that sends none refusing one. PKCE is on, `S256` by default (`pkce_enabled`, `pkce_method`).
The user is read from the `userinfo` endpoint or from the `id_token` claims, by
`user_data_source`; `signature_verifier_algorithms` verifies the ID token against the
provider's keys, and `None` reads its claims without verifying. The callback answers on
`check_path` (`/oidc/callback` by default), `scope` adds to the always-asked `openid`,
`max_age` bounds how old an authentication may be, and `authorization_params` carries extra
parameters — the ones the flow manages are guarded so no configuration can set them.

Three sub-blocks ride on the login:

- `token_generator` (`OidcTokenGeneratorConfig(algorithms, keyset, audience, issuers, claim)`)
  mints this application's own tokens through the `security:oidc:generate-token` command,
  registered only when a console is active and at least one firewall mints:
  `security:oidc:generate-token <user-identifier>`, `--firewall` naming which when several
  mint, `--algorithm` and `--issuer` the choice when several are declared, `--ttl` and
  `--not-before` the token's lifetime and start.
- `backchannel_logout` (`OidcBackChannelLogoutConfig(route, …)`) and `end_session`
  (`OidcEndSessionConfig(post_logout_redirect_path=…)`) wire the provider-pushed logout —
  see *The OIDC back channel* below.
- A token-refresh listener joins the firewall's chain, ordered after the context step,
  renewing the access token of a login whose expiry falls within the refresher's leeway.

### Remember me

`RememberMeConfig(secret=…)` builds the remember-me login: a request presenting the cookie a
previous login left is logged back in, lazily — the factory's priority `-100` puts it behind
the interactive authenticators, so a fresher proof always wins. `handler` picks how the cookie
is held: `"signature"` (the default) signs the value over the user's covered properties, so a
changed password retires every cookie; `"persistent"` keeps a series per cookie through the
application's `TokenProviderInterface` service (from `xtr_security_core`), named by qualifier
in `token_provider` — refused by name at wiring when the persistent handler is asked for
without one. The cookie's shape is `name` (`REMEMBERME`), `lifetime` (a year), `path`,
`domain`, `secure`, `httponly`, `samesite`; the ask is `always_remember_me`, or the request's
`remember_me_parameter` (`_remember_me`). `signature_properties` names the user properties
whose digest a persisted value carries (the password by default). The `secret` the signature
rides on is a configuration field — read it from the environment, the way *Secrets* below
shows; never generate one. The handler itself is a service, qualified
`<firewall>#remember_me_handler`, addressed with `Target` wherever a cookie is minted or
cleared by hand.

### Login links

`LoginLinkConfig(path, check_path, …)` builds the login-link authenticator: a link minted
through the firewall's own handler service signs its user in when followed. The handler —
`LoginLinkHandlerInterface`, qualified `<firewall>#login_link_handler` — is what an
application mints through. `path` is the literal path every minted link leads to and
`check_path` the literal path a followed link arrives at, both required; `lifetime` counts
600 seconds by default; `check_post_only` demands a POST of the follow;
`signature_properties` (the password by default) retires every link of a user when any of
them changes. The `secret` the hash is signed with is a configuration field, read from the
environment — never generated. The success and failure handlers follow the form login's
pattern.

## Access-token authenticators

`AccessTokenConfig(token_handler, token_extractors=("header",), realm=None,
resource_metadata_uri=None, sender_constraint=None)`. Extractors are `"header"`, `"query"`
and `"body"`, tried in order; the first one's scheme documents the firewall in the generated
schema. `realm` is named in the `WWW-Authenticate` challenge, and the `resource_metadata_uri`
(RFC 9728) is advertised in every challenge. A `sender_constraint` (a
`SenderConstraintInterface`) weighs the request against what the token says it is bound to
before anything is loaded on the user's behalf, and names the scheme and the parameters every
challenge answers with.

| Configuration | Key | Verifies |
| --- | --- | --- |
| `ServiceTokenHandlerConfig(service=MyTokenHandler, qualifier=None)` | `id` | with a handler you registered as a service |
| `Oauth2TokenHandlerConfig(introspection_base_uri, credentials=…, …)` | `oauth2` | a token by introspecting it with its authorization server (RFC 7662) |
| `OidcTokenHandlerConfig(issuers=(…), audience="…", keyset=… \| discovery_uri=… \| jwks_uri=…)` | `oidc` | a third-party OIDC issuer's tokens; needs the `oidc` extra |
| `OidcUserInfoTokenHandlerConfig(userinfo_base_uri, claim="sub", …)` | `oidc_user_info` | a token by presenting it to the issuer's userinfo endpoint; needs the `oidc` extra |

`OidcTokenHandlerConfig` takes **exactly one** key source, and at least one issuer and an
audience; `algorithms` default to `("RS256",)`, `claim` to `"sub"`, plus `leeway` (0 to 300
seconds), `enforce_at_jwt_type` and `allow_insecure_http`. `exp` is required on a token: one that
never expires is refused.

`Oauth2TokenHandlerConfig` reaches the introspection endpoint through a scoped client over
`introspection_base_uri` with this resource server's `credentials`, or through the `client`
service the application registered; `audiences` and `issuer` are checked only when given, a
`cache` service keeps active responses for `cache_ttl` seconds, and
`signed_response_algorithms` asks for the response as a signed JWT — verified against
`signed_response_keyset`, or against the keys the issuer's metadata publishes, read through
the `signed_response_discovery_cache` service (which needs `issuer`). A signed response needs
the `oidc` extra. `OidcUserInfoTokenHandlerConfig` reads the endpoint from
`userinfo_base_uri` — or from the issuer's discovery document through the `discovery_cache`
service, kept under `discovery_cache_key` — and the identifier from `claim` (`sub` by
default).

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

## Logout

`LogoutConfig(path="/logout", target_path="/", enable_csrf=False, csrf_parameter="_csrf_token",
csrf_token_id="logout", clear_site_data=None, cookie_clearing={}, invalidate_session=True,
clear_csrf_tokens=False)` parks a logout step on the firewall's context: the request asking
for `path` is logged out, its token cleared, and the `LogoutEvent` it announces is answered on
the firewall's own dispatcher by the listeners the configuration turns on — the default
redirect to `target_path`, the `Clear-Site-Data` header, the configured cookies cleared (each
a `ClearedCookie` from `xtr_security_http`), and the session invalidated on a stateful
firewall. `enable_csrf` has the step prove the request with the forgery-token manager before
it logs out; `clear_csrf_tokens` drops every token the request's session minted. Both need
the session the tokens are stored in, so a stateless firewall asking for either fails the
build saying so.

One `LogoutUrlGenerator` service (from `xtr_security_http`) carries every firewall's
registration, so whatever renders a page asks for a logout's address by the firewall's name —
or with none, resolved over the current request's token. The generator is scoped to the
request, so what one request named never answers for the next.

## Switch user

`SwitchUserConfig(role="ROLE_ALLOWED_TO_SWITCH", parameter="_switch_user", enable_csrf=False,
csrf_parameter="_csrf_token", csrf_token_id="switch_user", path=None)` parks the switch step
on the firewall's chain: a caller holding the `role` (weighed against the target user as the
subject) becomes another user by carrying `parameter` — on any page the firewall claims, or
on the dedicated `path` — and steps back out with the same parameter carrying `_exit`.
`enable_csrf` asks for a forgery token under `csrf_parameter` and `csrf_token_id`, refused on
a stateless firewall, which has no session to keep the tokens in. The bundle hands the step
the firewall's own dispatcher, so the `SwitchUserEvent` it announces — before a switch
settles, and before an exit restores the original token — reaches the listeners of
`firewall_dispatcher_name(firewall)` beside the firewall's other events. One scoped
`ImpersonateUrlGenerator` service (from `xtr_security_http`) renders the addresses a page
switches by — the impersonation and exit paths, URLs and forms.

## Login throttling

`LoginThrottlingConfig(secret=…, global_limit=5, global_interval="15 minutes", local_limit=5,
local_interval="15 minutes")` counts the firewall's login attempts: `global_limit` per
`global_interval` from one client address, `local_limit` per `local_interval` from one account
at one address — the global count surviving any one account's success, so one client may not
farm a whole directory. The counts live in the application's `StorageInterface` service (from
`xtr-rate-limiter`), and the keys are HMAC prefixes over the `secret`, so a shared store keeps
no readable account or address — the `secret` a configuration field, read from the
environment, never generated. The listener runs on the firewall's dispatcher at `2080`, ahead
of the provider's `2048` — a request already over the limit is refused before any user is
loaded or any password verified.

## Cross-site request forgery

The forgery machinery is opt-in: it is wired when a firewall's configuration asks for a token,
through one of four triggers — a form login with `enable_csrf`, a logout with `enable_csrf`
or `clear_csrf_tokens`, a `switch_user` block with `enable_csrf`, or the firewall's
`csrf_route_markers` — and nothing registers without an ask. The bundle then builds the csrf
package's manager over the session the request reattached, as the application's one
`CsrfTokenManagerInterface` service: the route marker's checker (`IsCsrfTokenValid`) survives
on its arrival, and the passport check settles the badge a form login mints, ahead of the
credential check. The tokens themselves travel in the session — so a stateless firewall
declaring the markers, or a switch asking for a proof on one, fails the build — and a
migration empties them with the session it rotates.

## Secrets

Three configurations sign or derive with a secret: the remember-me cookie (`secret`), the
login link (`secret`) and the login throttling (`secret`). Each is a plain configuration
field, so the application's own `configure` reads it from the environment the way every other
setting of the application is read:

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

The bundle never mints one: it builds and boots without any of them — the console still runs,
so a secret can be generated or inspected — and the service that needs one fails the first
time it is asked for, naming the setting: the login-link handler refusing `secret` on the
login-link configuration, the throttling listener refusing `secret` on the login-throttling
configuration, the remember-me handler the same on the remember-me configuration. An empty
value reads as no secret at all.

## The OIDC back channel

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
carrying nothing of the browser that logged in — and a refusal answers the bare `400` with no
detail: the reason is the verifier's to name in the log, not the caller's to read.

## `AccessControlConfig`

`AccessControlConfig(path, attribute, host=None, methods=(), ips=(), channel=None,
firewall=None)`. `path` and `host` are regular expressions, searched against the request —
`path` below the application's mount with per-cent escapes undone, `host` without regard to
case. An `ips` entry is an address or a network, written in CIDR or netmask form. One
attribute per rule, by design: a rule needing two conditions is two rules, or one closure
attribute. A rule may also name a `channel` — `"https"` or `"http"` — the request must arrive
over; a matching request arriving over the wrong one is not decided at all but redirected, by
the channel step below.

## The channel

A firewall whose access rules carry a channel parks the channel step first on its chain —
ahead of the context step and the manager's own, so nothing a request carries is restored,
authenticated or decided before it arrives the way the rule demands. The step answers a
request arriving over the wrong scheme with a `301` to the same request over the demanded
one: the host, path and query kept, the target scheme's port spelled out from the
configuration's `http_port`/`https_port` when it is not the scheme's default. The scheme a
request is read by is its URI's own — there is no trusted-proxy machinery to weigh a
forwarded header — so an application behind a proxy that terminates the encryption reads
plain `http` here; a rule with no channel parks no step.

## Firewall listeners

A firewall's listener chain — steps implementing `FirewallListenerInterface` (from
`xtr_security_http`), each declaring its `get_priority()` — is put in running order by the
bundle's sorting pass: higher priority first, the gathering order for listeners that share
one, and a listener's `@FirewallListenerOrder(before=..., after=...)` declaration settling how
it stands against its neighbours within a shared priority — a constraint that would cross a
priority fails the build, naming the firewall. Name a listener's qualifier in the firewall's
`listeners` to park it on the chain.

Every secured firewall's chain carries its own authentication step — the
`AuthenticatorManagerListener` running that firewall's authenticator manager — registered by
the bundle under `firewall_manager_listener_name(firewall)` and parked ahead of the listeners
the `listeners` configuration names, so no application names it itself; a
`@FirewallListenerOrder` constraint addresses it by that qualifier to stand against it. The
chain carries the firewall's access step the same way: an `AccessListener` over the request's
token storage, the decision manager and the firewall's own access map, registered under
`firewall_access_listener_name(firewall)` and ordered by its `-255` priority after the
authentication step.

## User providers

| Configuration | Loads a user from |
| --- | --- |
| `InMemoryUserProviderConfig(users={identifier: {"password": …, "roles": (…), "enabled": True}})` | the table written inline |
| `ChainUserProviderConfig(providers=("db", "ldap"))` | each named provider in turn; needs at least one |
| `ServiceUserProviderConfig(service=MyUserProvider, qualifier=None)` | a provider the container provides |

Write your own by implementing `UserProviderInterface` from `xtr_security_core`:
`load_user_by_identifier(identifier)` (raising `UserNotFoundError`), `refresh_user(user)`
(reloading a user held from an earlier request; raising `UnsupportedUserError` for a class it
does not load) and `supports_class(user_class)`. Register it `@as_service` and name it with
`ServiceUserProviderConfig`. Implement `PasswordUpgraderInterface` as well and the password
migrating listener re-stores a rehashed password for you after a successful sign-in.

A configured provider is also injectable by name:

```python
from typing import Annotated

from xtr_dependency_injection import Target
from xtr_security_core import InMemoryUserProvider

users: Annotated[InMemoryUserProvider, Target("users")]
```

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

Each firewall dispatches eleven events on a dispatcher of its own: `CheckPassportEvent`,
`AuthenticationTokenCreatedEvent`, `AuthenticationSuccessEvent`, `InteractiveLoginEvent`,
`LoginSuccessEvent`, `LoginFailureEvent`, `CheckRefreshedUserEvent`,
`TokenDeauthenticatedEvent`, `SwitchUserEvent`, `LogoutEvent` and
`OidcAuthorizationRequestEvent` — all from `xtr_security_http` but
`AuthenticationSuccessEvent`, which lives in `xtr_security_core`. A listener of them on the main
dispatcher hears every firewall; to hear one alone, name its dispatcher:

```python
from xtr_event_dispatcher import as_event_listener
from xtr_security_http import LoginSuccessEvent
from xtr_security.bundle import firewall_dispatcher_name


@as_event_listener(dispatcher=firewall_dispatcher_name("api"))
def count_api_login(event: LoginSuccessEvent) -> None: ...
```

In debug mode `debug:event-dispatcher --dispatcher security.event_dispatcher.api` lists that
firewall's listeners.

## Challenges

The exception listener answers for you — one per firewall, built from that firewall's parts:
an `AuthenticationError` becomes the firewall's entry-point challenge, or a bare `401` with
`WWW-Authenticate: Bearer`; an `AccessDeniedError` becomes `403`, or the entry-point
challenge when the caller is not fully authenticated, or an `insufficient_scope` challenge
when a scope was the denied attribute. A recency refusal (`IS_AUTHENTICATED_RECENTLY`) from a
known caller is answered with a re-authentication when the firewall's
`re_authentication_entry_point` names a `ReAuthenticationEntryPointInterface` service — the
fresh proof the recency check asks for, handed to the listener the way the denial handlers
are — and the interrupted path is kept on the session for the return trip unless the
firewall is stateless or the entry point only stands in
(`FallbackAuthenticationEntryPointInterface`).

## Adding a kind of authenticator

Only a library shipping its own bundle needs this. Implement `AuthenticatorFactoryInterface`
(a `key`, a `priority`, a `config_type` and `create_authenticator(...)`) and prepend it onto the
security configuration from the bundle's `prepend_extension` hook with `add_authenticator_factory`.
A factory whose authenticator can do without a user provider inherits
`StatelessAuthenticatorFactoryInterface`: it is handed no provider, rather than a
`MissingUserProvider`, when the application configures none.
`add_token_handler_factory` and `add_user_provider_factory` are the same seam for the other two
registries. An application configures what those factories accept; it does not write factories.
