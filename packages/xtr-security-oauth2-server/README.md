<div align="center">

# xtr-security-oauth2-server

**An OAuth 2.0 authorization server and resource-server authenticator for xtr security.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

The [security family](../xtr-security) authenticates a request that already carries a credential,
and [xtr-security-jwt](../xtr-security-jwt) signs tokens for an application's own users — neither
issues a token to a *third party*. This package is that half: an authorization server an
application hosts, which registers clients, runs the OAuth 2.0 grants against them, issues access
and refresh tokens, and a firewall authenticator that accepts those tokens back on a protected
route.

It is the bundle package over [xtr-security-oauth2-server-core](../xtr-security-oauth2-server-core),
the protocol library, and ships everything around it an application would otherwise write:

- 🔑 **The flows** — client credentials, authorization code with proof key (required of a client
  holding no secret), refresh token with rotation, and the device flow; password and implicit
  ship off.
- 🌐 **The endpoints** — `/authorize`, `/token`, `/device-code`, `/revoke` (RFC 7009),
  `/introspect` (RFC 7662), the RFC 8414 description and the published key set, added by
  `setup(app, kernel)` and arranged in a routes file.
- 🔥 **A firewall key `oauth2`** — `OAuth2AuthenticatorConfig()` on a firewall accepts the access
  tokens (RFC 9068) this server signs; their scopes become roles and `Firewall.scoped()` checks.
- 🗄️ **Stores** — in memory, in a database through [xtr-orm](../xtr-orm) (the mapping ships, the
  revision is the application's), or the application's own.
- 🗣️ **Events** — consent, scopes, users, extra claims and the token answer are each a question
  an application answers in a listener.
- 🛠️ **Commands** — mint the signing key pair, administer clients, sweep what expired.

## Install

```sh
uv add xtr-security-oauth2-server              # the server, its bundle and its endpoints
uv add "xtr-security-oauth2-server[orm]"       # + clients and credentials in a database
uv add "xtr-security-oauth2-server[console]"   # + the oauth2-server:* commands
```

Requires Python 3.11+. It brings the protocol library, the security family, xtr-security-jwt's
key layer, the password hasher, the clock, the event dispatcher and the HTTP kernel with it.

## Quick start

A server issuing tokens to a service (client credentials) and to a browser application acting
for a person (authorization code), and an API accepting them. The person signs in with a
self-issued token in a cookie, which is what [xtr-security-jwt](../xtr-security-jwt) is for.

### 1. List the bundles and mint the keys

```python
# app/bundles.py
from xtr_security_jwt.bundle import JwtBundle
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle

BUNDLES = {OAuth2ServerBundle: {"all": True}, JwtBundle: {"all": True}}
```

```console
$ oauth2-server:generate-keypair              # where OAUTH2_SERVER_PRIVATE_KEY_PATH points
$ jwt:generate-keypair --kid jwt --output-dir secrets
$ python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='))"
```

The second line writes `secrets/jwt.pem` and its public `secrets/jwt.jwks.json`: point
`JWT_SECRET_KEY_PATH` at `secrets/jwt.pem`, the key the `jwt` configuration in step 3 signs the
person's sign-in token with.

The last line is the value of `OAUTH2_SERVER_ENCRYPTION_KEY`, which authorization codes and refresh
tokens are sealed with; it is a different key from the pair access tokens are signed with.

### 2. Say who the server is

```python
# app/config/oauth2_server.py
from xtr_dependency_injection import configure, env
from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)


@configure
def oauth2_server() -> OAuth2ServerConfig:
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            issuer="https://authorization.example.com",
            private_key=env("resolve:OAUTH2_SERVER_PRIVATE_KEY_PATH"),
            encryption_key=env("OAUTH2_SERVER_ENCRYPTION_KEY"),
            encryption_key_type="key",
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(
            available=("invoices:read", "invoices:write"), default=("invoices:read",)
        ),
        persistence=InMemoryPersistenceConfig(),
    )
```

### 3. Write the firewalls

```python
# app/config/security.py
from xtr_dependency_injection import configure, env
from xtr_security.bundle import AccessControlConfig, FirewallConfig, SecurityConfig
from xtr_security_jwt.bundle import (
    AuthorizationHeaderExtractorConfig,
    CookieExtractorConfig,
    JwtAuthenticatorConfig,
    JwtConfig,
    JwtUserProviderConfig,
    TokenExtractorsConfig,
)
from xtr_security_oauth2_server.bundle import OAuth2AuthenticatorConfig


@configure
def jwt() -> JwtConfig:
    # The end user's own sign-in: a self-issued token in a cookie.
    return JwtConfig(
        secret_key=env("resolve:JWT_SECRET_KEY_PATH"),
        token_extractors=TokenExtractorsConfig(
            authorization_header=AuthorizationHeaderExtractorConfig(enabled=False),
            cookie=CookieExtractorConfig(enabled=True, name="session"),
        ),
    )


@configure
def security() -> SecurityConfig:
    return SecurityConfig(
        providers={"people": JwtUserProviderConfig()},
        firewalls={
            # 1. The person answering a consent question signs in here.
            "login": FirewallConfig(
                pattern=r"^/authorize",
                provider="people",
                authenticators=(JwtAuthenticatorConfig(),),
            ),
            # 2. The API accepts this server's access tokens.
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="people",
                authenticators=(OAuth2AuthenticatorConfig(),),
            ),
            # 3. No firewall claims /token, /revoke, /introspect, /device-code or
            #    /.well-known/*: the server authenticates the client there itself.
        },
        access_control=(
            AccessControlConfig(path=r"^/(authorize|api)", attribute="IS_AUTHENTICATED"),
        ),
    )
```

### 4. Answer the consent question, and register the clients

```python
# app/consent.py
from typing import Annotated

import anyio.to_thread
from xtr_dependency_injection import Injected, Target, on_boot
from xtr_event_dispatcher import as_event_listener
from xtr_password_hasher import PasswordHasherInterface
from xtr_security_oauth2_server.event.authorization_request_resolve_event import (
    AuthorizationRequestResolveEvent,
)
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope


@as_event_listener(OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE)
async def approve_known_clients(event: AuthorizationRequestResolveEvent) -> None:
    # A real deployment shows a consent page with event.set_response(...) on the first
    # pass, and approves when the form posts the original query back.
    if event.get_client().get_identifier() == "dashboard":
        _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)


@on_boot
async def register_demo_clients(
    clients: Injected[ClientManagerInterface],
    hasher: Annotated[PasswordHasherInterface, Target("oauth2_server")],
) -> None:
    # In memory, clients are registered at every start; a database keeps them.
    billing = Client("Billing", "billing", await anyio.to_thread.run_sync(hasher.hash, "s3cret"))
    _ = billing.set_grants(Grant("client_credentials")).set_scopes(Scope("invoices:read"))
    dashboard = Client("Dashboard", "dashboard", None)  # public: it holds no secret
    _ = dashboard.set_grants(Grant("authorization_code"), Grant("refresh_token"))
    _ = dashboard.set_redirect_uris(RedirectUri("https://dashboard.example.com/callback"))
    for client in (billing, dashboard):
        _ = client.set_active(True)
        await clients.save(client)
```

A request is denied until a listener approves it. With a database store, register clients with
`oauth2-server:create-client` instead, which prints the secret once and stores only its hash.

### 5. Serve it

```python
# main.py — beside the app package, so the kernel's scan does not import it
from typing import Annotated

from fastapi import FastAPI, Response
from xtr_dependency_injection import Injected, Kernel
from xtr_http_kernel import setup
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser, Firewall
from xtr_security_jwt import JwtTokenManagerInterface

app = FastAPI(dependencies=[Firewall()])


@app.post("/login")
async def login(
    identifier: str, tokens: Injected[JwtTokenManagerInterface], response: Response
) -> None:
    user = InMemoryUser(identifier, roles=["ROLE_USER"])  # the application checks the password
    response.set_cookie("session", await tokens.create(user), httponly=True, secure=True)


@app.get("/api/invoices", dependencies=[Firewall("api").scoped("invoices:read")])
async def invoices(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, str]:
    return {"caller": user.get_user_identifier()}


kernel = Kernel("app", concurrent_scoped_access=True)
setup(app, kernel)
```

The unbound `Firewall()` on the application is what runs the firewalls in front of the endpoints
`setup` adds, which carry no dependency of their own: without it `/authorize` is reached with
nobody signed in and answers `access_denied`. The description and the key set stay at the fixed
paths RFC 8414 puts under the issuer; the other endpoints can move — see [Endpoints](#endpoints).

```console
$ curl -s -u billing:s3cret -d grant_type=client_credentials -d scope=invoices:read \
    https://authorization.example.com/token
{"token_type": "Bearer", "expires_in": 3599, "access_token": "eyJ…", "scope": "invoices:read"}

$ curl -s -H "Authorization: Bearer eyJ…" https://authorization.example.com/api/invoices
{"caller": "billing"}
```

The dashboard sends the browser to `/authorize?response_type=code&client_id=dashboard&…` with an
S256 `code_challenge`; signed in, the person is approved by the listener and redirected back with
a `code`, which the dashboard redeems at `/token` with its `code_verifier` for an access token and
a refresh token.

## Configure

`OAuth2ServerConfig` is a frozen dataclass buildable with no arguments, and the bundle builds and
boots on it — the console included, which is how the key pair and the clients a fresh application
lacks are made. Nothing is issued until a deployment supplies what only it can: each of
`authorization_server.private_key`, `.encryption_key`, `.issuer`, `scopes.available`,
`persistence` and — while the device flow is on — `authorization_server.device_code_verification_uri`
is reported by the first service that cannot be built without it, as an
`InvalidConfigurationError` naming the setting and `<app>/config/oauth2_server.py`. Nothing is
ever minted on the deployment's behalf.

| Field | Default | What it is |
|---|---|---|
| `authorization_server` | `AuthorizationServerConfig()` | What signs, seals, issues and runs — below |
| `resource_server` | `ResourceServerConfig()` | How an API verifies the tokens |
| `scopes` | `ScopesConfig()` | The scopes this deployment knows |
| `persistence` | `None` | Where clients and credentials live: one of the three below. Required |
| `client` | `ClientConfig()` | Which class registered clients are |
| `role_prefix` | `"ROLE_OAUTH2_"` | What a scope becomes a role under: `invoices:read` grants `ROLE_OAUTH2_INVOICES:READ`. Never empty |

`AuthorizationServerConfig`:

| Field | Default | What it is |
|---|---|---|
| `issuer` | `None` | The origin every token claims as `iss` and the description names. An origin only — no path, query or fragment |
| `private_key` | `None` | The key access tokens are signed with, as PEM text or a file path |
| `private_key_passphrase` | `""` | The pass phrase that key is encrypted with |
| `encryption_key` | `None` | What authorization codes and refresh tokens are sealed with |
| `encryption_key_type` | `"plain"` | `"plain"`: a password of at least 32 characters, stretched once when the server is built. `"key"`: the base64url of 32 random bytes, used as is |
| `audience` | `None` | The `aud` access tokens carry and the resource server requires; `None` addresses each token to its client and checks none |
| `signature_algorithm` | `"RS256"` | How access tokens are signed |
| `additional_public_keys` | `()` | Files of further public keys tokens verify against, for rotation |
| `access_token_ttl` / `refresh_token_ttl` | 1 hour / 30 days | `timedelta`s, positive |
| `auth_code_ttl` / `device_code_ttl` | 10 minutes / 10 minutes | `timedelta`s, positive |
| `enable_client_credentials_grant`, `enable_auth_code_grant`, `enable_refresh_token_grant` | `True` | The flows on by default |
| `enable_device_code_grant` | `True` | The device flow; it needs `device_code_verification_uri`, so turn it off or name one |
| `enable_password_grant`, `enable_implicit_grant` | `False` | The two flows the protocol withdrew |
| `require_code_challenge_for_public_clients` | `True` | A client holding no secret must send a proof key |
| `persist_access_token` | `True` | Whether access tokens are stored. Off, one cannot be revoked before it expires: `/revoke` still answers 200, and `/introspect` keeps calling it active |
| `revoke_refresh_tokens` | `True` | Whether redeeming a refresh token spends it |
| `response_type_class` | `None` | The class the token endpoint answers with, built by the container; `None` for the bearer answer |
| `device_code_verification_uri` | `""` | The page a person types the user code into — the application's |
| `enable_device_code_verification_uri_complete_generation` | `True` | Also send the URI with the code in it |
| `device_code_polling_interval` | `5` | Seconds a device waits between polls |
| `enable_device_code_polling_interval_visibility` | `True` | Tell the device that interval |
| `enable_revocation_endpoint` | `True` | `/revoke` |
| `enable_introspection_endpoint` | `False` | `/introspect`, off: it answers about tokens issued to other clients |
| `enable_metadata_endpoint` | `True` | `/.well-known/oauth-authorization-server` |

`ResourceServerConfig(public_key=None, jwt_leeway=None)`: the verifying key — derived from the
signing key when `None`, which is the common case — and a `timedelta` widening the expiry window
for clocks that disagree. `ScopesConfig(available=(), default=())`: every scope a client may ask
for, and the ones a client registered naming none is given; `default` must be within `available`
and may be empty. `ClientConfig(classname=Client)`: a subclass of `AbstractClient`, for a
deployment owning its client table.

`persistence` is one of three:

| Config | What it registers |
|---|---|
| `InMemoryPersistenceConfig()` | Stores in this process, forgotten when it ends. Tests and demonstrations; a refresh token's single use holds only within one process |
| `OrmPersistenceConfig(connection="default", table_prefix="oauth2_")` | The managers on an [xtr-orm](../xtr-orm) connection, and the tables joining that connection's definitions: `oauth2_authorization_code` and `oauth2_refresh_token` always, `oauth2_access_token` while access tokens are persisted, `oauth2_device_code` while the device flow is on, `oauth2_client` unless the application owns its client class. Needs the `orm` extra and `OrmBundle` listed; the application writes the revision with `orm:migrations:diff` |
| `CustomPersistenceConfig(access_token_manager=…, authorization_code_manager=…, client_manager=…, refresh_token_manager=…, device_code_manager=…, credentials_revoker=…)` | Nothing of its own: each manager interface is aliased to the application's service named here. All six are required, and each must be a registered service |

An application owning its client class writes it on its own declarative base with
`ClientMappingMixin`, which maps `AbstractClient`'s registration onto it, and names it under
`client.classname`; the token tables then point at its table instead of `oauth2_client`. The
type checker needs two suppressions there — the base brings a constructor the model's own
replaces, and the mixin maps columns onto attributes the model already declares:

```python
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from xtr_security_oauth2_server.model.abstract_client import AbstractClient
from xtr_security_oauth2_server.persistence.mapping import ClientMappingMixin


class Base(DeclarativeBase): ...


class AppClient(  # pyright: ignore[reportUnsafeMultipleInheritance, reportIncompatibleVariableOverride]
    ClientMappingMixin,
    AbstractClient,
    Base,
):
    __tablename__ = "app_client"

    _identifier: Mapped[str] = mapped_column(  # pyright: ignore[reportIncompatibleVariableOverride]
        "identifier", String(32), primary_key=True
    )
    tenant: Mapped[str | None] = mapped_column("tenant", String(32), nullable=True)
```

On a base whose primary key is its own (`UUIDAuditBase`, say), `_identifier` is a `unique`,
not-null column instead. One client class per process.

## Endpoints

`setup(app, kernel)` adds every endpoint, contributed by two route loaders: resource
`oauth2_server` (authorize, token, device-code, revoke, introspect) and resource
`oauth2_server_well_known` (the description and the key set, which RFC 8414 places under the
issuer, so they cannot take a prefix). An endpoint a deployment turned off answers `404`. A
routes file in `<app>/config/routes/` moves them or leaves some out —
`routes.import_("oauth2_server").prefix("/auth").exclude("oauth2_introspect")` — and the
description publishes each endpoint wherever it ends up, leaving out the ones excluded:

| Method | Path | Route name | Answers when |
|---|---|---|---|
| `GET`, `POST` | `/authorize` | `oauth2_authorize` | always; behind the application's own sign-in firewall |
| `POST` | `/token` | `oauth2_token` | always |
| `POST` | `/device-code` | `oauth2_device_code` | `enable_device_code_grant` |
| `POST` | `/revoke` | `oauth2_revoke` | `enable_revocation_endpoint` |
| `POST` | `/introspect` | `oauth2_introspect` | `enable_introspection_endpoint` |
| `GET` | `/.well-known/oauth-authorization-server` | `oauth2_metadata` | `enable_metadata_endpoint` |
| `GET` | `/.well-known/jwks.json` | `oauth2_jwks` | always |

- **`/authorize`** reads the request, refuses an unhashed proof key unless the client is
  registered for one, and asks `OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE` about the person
  `Security.get_user()` returns. Consent is stateless: the page a listener answers with posts the
  original query back to `/authorize`, and the second pass is the one approved. Binding that form
  to the person it was shown to (a CSRF token) is the listener's. With nobody signed in the client
  is told only `access_denied`, and the cause is written on the `oauth2_server` log channel.
- **`/token`, `/revoke`, `/introspect`** authenticate the client themselves — HTTP Basic or
  `client_id`/`client_secret` in the form — so no firewall claims them. A revoked refresh token
  takes its access token with it; a token that is unknown or another client's is answered as one
  just revoked.
- **`/device-code`** issues the pair a device polls with; the page the person types the user code
  into is the application's, and calls `AuthorizationServer.complete_device_authorization_request`
  (see the [skill](src/xtr_security_oauth2_server/.agents/skills/xtr-security-oauth2-server/SKILL.md)).
  Limit how often that page may be guessed at — a user code is 8 characters of 20 — with
  [xtr-http-kernel's](../xtr-http-kernel#rate-limits) `RateLimited`.
- **The description** names, under the configured issuer, the endpoints served, the grants the
  server runs — one the application or an add-on registered among them — the scopes and the
  proof-key methods; **the key set** publishes the signing key's public half and every additional
  public key, each under the `kid` a token's header names.

## Services

`OAuth2ServerBundle` registers, under the interfaces an application injects:

| Service | Interface / key | What it does |
|---|---|---|
| `AuthorizationServer` | itself | Runs the enabled grants: `/authorize`, `/token`, `/device-code` |
| `TokenServer` | itself | Answers `/revoke` and `/introspect` |
| `ResourceServer` | itself | Reads a bearer token off a request — what the `oauth2` authenticator uses |
| `BearerTokenValidator` | `AuthorizationValidatorInterface` | Judges an access token: signature, `typ`, window, `iss`, `aud`, revocation |
| `BearerTokenResponse` | `ResponseTypeInterface` | The token answer, or `response_type_class` |
| `ClientManagerInterface`, `AccessTokenManagerInterface`, `RefreshTokenManagerInterface`, `AuthorizationCodeManagerInterface`, `DeviceCodeManagerInterface` | the interfaces | The stores of the chosen persistence |
| `CredentialsRevokerInterface` | the interface | Withdraws everything issued to a client or a user — database and application stores only |
| `ScopeManagerInterface` | the interface | The configured vocabulary of scopes, always in memory |
| `ClientRepository`, `AccessTokenRepository`, `AuthCodeRepository`, `RefreshTokenRepository`, `DeviceCodeRepository`, `ScopeRepository`, `UserRepository` | the core's `*RepositoryInterface`s | The bridges between the protocol and the managers |
| `RawKeyLoader`, `JoserfcJwsProvider`, `PasswordHasherInterface` | qualifier `"oauth2_server"` | This server's own key material, and the hasher client secrets are kept under |

The key loader and JWS provider are never registered under the bare interfaces: `JwtBundle` owns
those, and a deployment commonly runs both, each with its own key. Ask for this server's with
`Annotated[KeyLoaderInterface, Target("oauth2_server")]`.

## Events

Every listener registers through [xtr-event-dispatcher](../xtr-event-dispatcher) under the same
name the code dispatches under — `@as_event_listener(OAuth2Events.X)`:

| Name | Event | A listener |
|---|---|---|
| `OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE` | `AuthorizationRequestResolveEvent` | Resolves the request (`resolve_authorization(APPROVED)`), or answers the browser (`set_response`) |
| `OAuth2Events.SCOPE_RESOLVE` | `ScopeResolveEvent` | Has the last word on the scopes a token carries (`set_scopes`) |
| `OAuth2Events.USER_RESOLVE` | `UserResolveEvent` | Checks a password-flow username and password and `set_user`s the owner |
| `OAuth2Events.ACCESS_TOKEN_EXTRA_CLAIMS_RESOLVE` | `AccessTokenExtraClaimsResolveEvent` | Adds claims to an access token before it is signed; the token's own names are refused |
| `OAuth2Events.TOKEN_REQUEST_RESOLVE` | `TokenRequestResolveEvent` | Replaces the token answer, refusals included |
| `OAuth2Events.PRE_SAVE_CLIENT` | `PreSaveClientEvent` | Changes a client before it is stored; the shipped listener hands a scope-less client `scopes.default` |

The protocol library announces five more, under `RequestEvent`'s names:
`ACCESS_TOKEN_ISSUED` and `REFRESH_TOKEN_ISSUED` (with `RequestAccessTokenEvent` and
`RequestRefreshTokenEvent`), `CLIENT_AUTHENTICATION_FAILED`, `USER_AUTHENTICATION_FAILED` and
`REFRESH_TOKEN_CLIENT_FAILED`.

## Commands

With the `console` extra and the console bundle active:

| Command | Does |
|---|---|
| `oauth2-server:generate-keypair [ALGORITHM] [--dry-run] [--skip-if-exists] [--overwrite]` | Mints the signing pair for the configured algorithm (or `RS*`, `PS*`, `ES*` 256–512, `EdDSA`) and writes it where `private_key` — and `resource_server.public_key`, when set — point: `0600` private, `0644` public, never through a link |
| `oauth2-server:create-client NAME [IDENTIFIER] [SECRET] [--redirect-uri …] [--grant-type …] [--scope …] [--public] [--allow-plain-text-pkce]` | Registers a client, minting what is left out, and prints the plaintext secret once; only its hash is stored |
| `oauth2-server:update-client IDENTIFIER [--add-/--remove-redirect-uri …] [--add-/--remove-grant-type …] [--add-/--remove-scope …] [--activate\|--deactivate]` | Amends a registration one change at a time |
| `oauth2-server:delete-client IDENTIFIER` | Withdraws a client |
| `oauth2-server:list-clients [--columns …] [--redirect-uri …] [--grant-type …] [--scope …]` | Lists the clients; a secret is never shown |
| `oauth2-server:clear-expired-tokens [-a] [-r] [-c] [-dc]` | Sweeps the expired access tokens, refresh tokens, codes and device codes — all of them when none is named. The one to schedule |

A client deactivated with `--deactivate` (or `set_active(False)` and a save) is refused as
`invalid_client` wherever it names itself — `/authorize`, `/token`, `/device-code`, `/revoke`,
`/introspect` — whether or not it holds a secret, so a refresh token it holds can no longer be
spent; an access token already issued to it stays good until it expires.

No command mints the encryption key; the one-liner in the Quick start does. With the in-memory
store, a client registered by a command is gone when the command exits.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add xtr-security-oauth2-server`; add `[orm]` to keep clients and credentials
  in a database, `[console]` for the commands.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate*, *Configure*, *Environment*
  and *Ignore* steps below, and no other: it lists `OAuth2ServerBundle`, writes a starting
  `<app>/config/oauth2_server.py`, `OAUTH2_SERVER_PRIVATE_KEY_PATH=%kernel.project_dir%/secrets/oauth2.pem`
  and a commented-out `OAUTH2_SERVER_ENCRYPTION_KEY` in `.env`, and adds `/secrets/*.pem` to
  `.gitignore`, and writes `<app>/config/routes/oauth2_server.py` serving every endpoint at its
  default path. It prints what a recipe cannot make for you: minting the key pair and the
  encryption key, naming this deployment's issuer, calling `setup`, the three firewalls,
  the listener that answers the consent question, registering a client, scheduling the sweep of
  what has expired, and the revision a database store takes.
- **Activate** — `OAuth2ServerBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
  from `xtr_security_oauth2_server.bundle` — and `JwtBundle` beside it when the end user signs in
  with a self-issued token. Then build the kernel with `concurrent_scoped_access=True` and call
  `setup(app, kernel)`, as the security family requires: it adds this server's endpoints. Put an
  unbound `Firewall()` on the application itself: the endpoints carry no dependency of their
  own, so that is what establishes the resource owner on `/authorize`.
- **Brings along** — the [security bundle](../xtr-security), the [clock](../xtr-clock), the
  [event dispatcher](../xtr-event-dispatcher) and the [HTTP kernel](../xtr-http-kernel) always,
  because this bundle requires them; the [logging](../xtr-logging) bundle when xtr-logging is
  installed, which is where an authorization request arriving with no resource owner is reported,
  on the `oauth2_server` channel; the [console](../xtr-console) bundle when xtr-console is
  installed, for the commands.
- **Configure** — with no configuration the bundle builds and boots, and issues nothing: a
  `<app>/config/oauth2_server.py` `@configure` function returning an `OAuth2ServerConfig` says who
  this server is (`authorization_server.issuer`), what it signs and seals with
  (`private_key`, `encryption_key`), which scopes it knows (`scopes.available`) and where its
  clients and credentials live (`persistence`). Each of those is reported, by name and with the
  file to write it in, by the first service that cannot be built without it — never by the build,
  which would take the console down with it. Three firewalls in `<app>/config/security.py`: one
  claiming `^/authorize` that signs the end user in (a `JwtAuthenticatorConfig()` reading a
  cookie, say); none claiming `/token`, `/revoke`, `/introspect`, `/device-code` or the
  `.well-known` paths, because authenticating the *client* there is this server's own job; and
  `OAuth2AuthenticatorConfig()` under the `authenticators` of the one in front of the API. A
  listener on `OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE` answers the consent question — see
  [Configure](#configure) and [Kernel / bundle](#kernel--bundle).
  `<app>/config/routes/oauth2_server.py` imports both route resources; move them or leave
  endpoints out there — see [Endpoints](#endpoints).
- **Environment** — `OAUTH2_SERVER_PRIVATE_KEY_PATH`, the file the written
  `config/oauth2_server.py` reads the signing key from with
  `env("resolve:OAUTH2_SERVER_PRIVATE_KEY_PATH")`; and `OAUTH2_SERVER_ENCRYPTION_KEY`, the
  base64url of 32 random bytes that authorization codes and refresh tokens are sealed with.
  Neither is read while the application builds, so it runs before they are set; a request then
  reports the one that is missing.
- **Ignore** — the key files the key pair is written to, when they are written under the project:
  `/secrets/*.pem`, which covers the private key and the public half
  `oauth2-server:generate-keypair` writes beside it when a deployment names a file for one.
- **Remove** — `uv run xtr-recipes recipes:remove xtr-security-oauth2-server`, then undo the steps
  it printed: the firewalls, the consent listener and the client registrations are the
  application's own.
- **Check** — `debug:bundles` lists `oauth2_server` as active; `debug:config oauth2_server` shows
  the resolved issuer, lifetimes, flows and store; and `GET
  /.well-known/oauth-authorization-server` answers with this server's description. With
  [xtr-console](../xtr-console) installed, `list oauth2-server` names the six commands this
  package ships — `oauth2-server:generate-keypair` mints the signing key pair where
  `OAUTH2_SERVER_PRIVATE_KEY_PATH` points, `oauth2-server:create-client`,
  `update-client`, `delete-client` and `list-clients` administer the clients, and
  `oauth2-server:clear-expired-tokens` sweeps what has expired, which is the one to run on a
  schedule.

## Kernel / bundle

```python
# app/bundles.py
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle

BUNDLES = {OAuth2ServerBundle: {"all": True}}
```

`OAuth2ServerBundle` (name `oauth2_server`, config `OAuth2ServerConfig`) requires the
[security](../xtr-security), [clock](../xtr-clock), [event dispatcher](../xtr-event-dispatcher)
and [HTTP kernel](../xtr-http-kernel) bundles, and the [logging](../xtr-logging) and
[console](../xtr-console) bundles when they are installed. No other bundle requires it, so it only
arrives by being listed. It:

- prepends onto the security configuration an authenticator factory keyed `oauth2`, which a
  firewall's `OAuth2AuthenticatorConfig()` builds — one authenticator per firewall, over that
  firewall's user provider;
- registers the stores of the chosen persistence, the protocol engine and one controller per
  endpoint, and the commands when the console bundle is active;
- tags every class subclassing the core's `GrantTypeInterface` with `GRANT_TAG`
  (`"oauth2_server.authorization_server.grant"`, attribute `access_token_ttl`), and its
  `GrantTypePass` enables each tagged grant on the server and has the description name it — the
  built-in ones are registered already tagged. No grant at all, or two answering the same grant
  type, is refused;
- collects services tagged `METADATA_TAG` (`"oauth2_server.metadata"`, attribute `priority`)
  implementing `MetadataContributorInterface` into the description, under this server's own
  fields;
- hands its tables to xtr-orm's `OrmMappingsPass` with the database persistence, and refuses that
  persistence when `OrmBundle` is not active.

It reads no key, issuer or store while building, so it builds and boots with no configuration.
An add-on — an identity layer, say — plugs in from its own bundle: it prepends
`authorization_server.response_type_class` and `enable_auth_code_grant=False`, registers an
`AuthCodeGrant` subclass tagged `GRANT_TAG`, and tags a metadata contributor; this bundle knows
nothing of it. The [skill's extending reference](src/xtr_security_oauth2_server/.agents/skills/xtr-security-oauth2-server/references/extending.md)
walks through one.

## Errors

Everything this package and the protocol library raise derives from `OAuth2Error`
(`xtr_security_oauth2_server_core.exception`), so one `except OAuth2Error` catches it all:

| Error | Base | Raised when |
|---|---|---|
| `OAuthServerError` | `OAuth2Error` | A request the protocol has a refusal for — `invalid_client`, `invalid_grant`, `access_denied`, `slow_down`, … — which the endpoints turn into the answer |
| `InvalidConfigurationError` | `OAuth2Error`, `ValueError` | A setting that cannot be used, or one missing where a service needs it, naming it and `<app>/config/oauth2_server.py` |
| `ClientAlreadyRegisteredError` | `OAuth2Error` | `oauth2-server:create-client`, or a store, met an identifier already registered |
| `OAuth2AuthenticationError` | `AuthenticationError`, `OAuth2Error` | The resource-server side refused a token; answered `401` with a bearer `invalid_token` challenge |
| `OAuth2AuthenticationFailedError` | `OAuth2AuthenticationError` | The one such refusal raised — the same for every unusable token, the cause kept |
| `InvalidArgumentError` | `OAuth2Error`, `ValueError` | One of the library's objects used wrongly — a reserved claim, an unreadable key |
| `UniqueTokenIdentifierConstraintViolationError` | `OAuthServerError` | A store met a token identifier already taken; the grant retries, and only a run of ten answers `500` |

The bundle's two live in `xtr_security_oauth2_server.exception`, the authentication ones in
`xtr_security_oauth2_server.security.exception`. A scope a route requires and the token lacks is
the family's `AccessDeniedError`, answered `403`.

## Layout

```
xtr_security_oauth2_server/
├── routing/                    the two route loaders setup() mounts the endpoints from
├── oauth2_events.py            OAuth2Events, the six names
├── authorization_server_metadata.py, metadata_contributor_interface.py
├── controller/                 one controller per endpoint
├── model/                      the stored client, tokens and codes, and their interfaces
├── value_object/               Grant, RedirectUri, Scope
├── entity/                     what the protocol is handed, built from the models
├── manager/                    the store interfaces, ClientFilter; in_memory/, orm/
│   └── null/                   an access-token manager storing nothing, for CustomPersistenceConfig
├── repository/                 the bridges the protocol library reads through
├── converter/                  scope and user conversions
├── persistence/                the ORM mapping (Driver, ClientMappingMixin) and column types
├── service/                    CredentialsRevokerInterface and the ORM revoker
├── event/, event_listener/     the events, and the default-scopes listener
├── security/                   OAuth2Authenticator, OAuth2Token, ClientCredentialsUser, errors
├── factory/                    the oauth2 authenticator factory
├── command/                    the oauth2-server:* commands
├── exception/                  InvalidConfigurationError, ClientAlreadyRegisteredError
├── recipe/                     what recipes:sync applies
└── bundle/                     OAuth2ServerBundle, its configuration and its passes
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-security-oauth2-server`; run the commands below from there. The conformance suite,
one module per RFC, is under `tests/conformance/`.

```sh
uv sync --all-packages --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest --cov
```

## License

MIT — see [LICENSE](LICENSE).
