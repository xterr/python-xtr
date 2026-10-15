---
name: xtr-security-oauth2-server
description: How to host an OAuth 2.0 authorization server with xtr-security-oauth2-server and its protocol library xtr-security-oauth2-server-core, and accept its access tokens on an API. Use when an application must issue tokens to third-party clients or services, run the client-credentials, authorization-code with PKCE, refresh-token, device, password or implicit flow, register or administer OAuth clients, show a consent page or approve an authorization request, protect an API with OAuth2AuthenticatorConfig or require a scope, publish the authorization-server metadata or JWKS, revoke or introspect a token, add a claim or a field to the token response, keep clients and tokens in memory, in a database with xtr-orm or in its own stores, own its client table, build an AuthorizationServer or ResourceServer by hand, write a custom grant or an add-on bundle on top of OAuth2ServerBundle, run the oauth2-server commands, or fix the InvalidConfigurationError naming a missing issuer, key, scope or persistence.
---

# xtr-security-oauth2-server

An authorization server an application hosts: it registers clients, runs the OAuth 2.0 grants
against them, issues signed access tokens (RFC 9068) and sealed refresh tokens, and a firewall
authenticator accepts those access tokens back. Two packages: `xtr-security-oauth2-server-core`
is the protocol library (servers, grants, entities, repositories, response types, the resource
server), buildable by hand; `xtr-security-oauth2-server` is its bundle, with stores, endpoints,
commands and the `oauth2` firewall key. This skill covers both.

It is an add-on of the security family: firewalls, voters and user providers are the
`xtr-security` skill's; the end user's own sign-in token is the `xtr-security-jwt` skill's.

## Quick reference

- List `OAuth2ServerBundle` in `<app>/bundles.py`; write `<app>/config/oauth2_server.py` with an
  `OAuth2ServerConfig` naming `issuer`, `private_key`, `encryption_key`, `scopes.available` and
  `persistence`. Each missing one is reported by the first service needing it.
- `setup(app, kernel)` adds every endpoint (resources `oauth2_server` and the fixed
  `oauth2_server_well_known`); move them or leave some out in `<app>/config/routes/oauth2_server.py`.
  Put an unbound `Firewall()` on the application — the endpoints carry no dependency of their own.
- Three firewalls: one claiming `^/authorize` that signs the end user in, none on `/token`,
  `/revoke`, `/introspect`, `/device-code` and `/.well-known/*`, and `OAuth2AuthenticatorConfig()`
  on the API's.
- A listener on `OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE` approves, denies or shows a consent
  page; a request is denied until one approves it.
- A scope becomes the role `ROLE_OAUTH2_<SCOPE>`; require one with `Firewall("api").scoped("x")`.
- `oauth2-server:generate-keypair` mints the signing pair; the encryption key is 32 random bytes,
  base64url, and no command mints it.
- Inject `AuthorizationServer`, `TokenServer`, `ResourceServer`, `ClientManagerInterface` and the
  other managers; this server's own key loader and hasher are under `Target("oauth2_server")`.
- Every error derives from `OAuth2Error` (`xtr_security_oauth2_server_core.exception`).

## Configure the server

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

- `issuer` is an origin only: the description lives at `/.well-known/oauth-authorization-server`
  under it, which is why `oauth2_server_well_known` cannot take a prefix.
- The device flow is on by default and needs `device_code_verification_uri` — name the page, or
  turn the flow off as above.
- `InMemoryPersistenceConfig()` forgets everything at exit; `OrmPersistenceConfig()` keeps it in
  an xtr-orm connection, `CustomPersistenceConfig(...)` in six services of the application's.

Every field and default: [references/configuration.md](references/configuration.md). Stores, the
tables and an application-owned client class: [references/persistence.md](references/persistence.md).

## Write the firewalls and serve the endpoints

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
            "login": FirewallConfig(
                pattern=r"^/authorize",
                provider="people",
                authenticators=(JwtAuthenticatorConfig(),),
            ),
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="people",
                authenticators=(OAuth2AuthenticatorConfig(),),
            ),
        },
        access_control=(
            AccessControlConfig(path=r"^/(authorize|api)", attribute="IS_AUTHENTICATED"),
        ),
    )
```

```python
# main.py — outside the app package, so the kernel's scan does not import it
from typing import Annotated

from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser, Firewall

app = FastAPI(dependencies=[Firewall()])


@app.get("/api/invoices", dependencies=[Firewall("api").scoped("invoices:read")])
async def invoices(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, str]:
    return {"caller": user.get_user_identifier()}


kernel = Kernel("app", concurrent_scoped_access=True)
setup(app, kernel)
```

- The `login` firewall needs `JwtBundle` listed too; any authenticator that establishes a person
  will do. With none, `/authorize` answers `access_denied` and logs why on `oauth2_server`.
- A token from the client-credentials flow names no person: the caller is a
  `ClientCredentialsUser` carrying the client's identifier and no roles of its own.
- A missing scope is `403 insufficient_scope`; no token is `401` with a bearer challenge.

## Answer the consent question

```python
from xtr_event_dispatcher import as_event_listener
from xtr_http_kernel.bridge import Response
from xtr_security_oauth2_server.event.authorization_request_resolve_event import (
    AuthorizationRequestResolveEvent,
)
from xtr_security_oauth2_server.oauth2_events import OAuth2Events


@as_event_listener(OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE)
async def ask_for_consent(event: AuthorizationRequestResolveEvent) -> None:
    if event.get_client().get_identifier() == "dashboard":  # a first-party client
        _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)
        return
    page = Response(200).with_header("content-type", "text/html")
    _ = await page.get_body().write(b"<form method='post'>Allow this client?</form>")
    _ = event.set_response(page)
```

Consent is stateless: the page posts the original query back to `/authorize`, and a listener
approves the second pass. Bind that form to the person it was shown to (a CSRF token you check
on the post) — nothing in this package does. `event.get_user()`, `get_scopes()`, `get_state()`
and `get_redirect_uri()` describe what is asked. More events, with a listener for each:
[references/events.md](references/events.md).

## Register and administer clients

```python
from typing import Annotated

import anyio.to_thread
from xtr_dependency_injection import Injected, Target, on_boot
from xtr_password_hasher import PasswordHasherInterface
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope


@on_boot
async def register_demo_clients(
    clients: Injected[ClientManagerInterface],
    hasher: Annotated[PasswordHasherInterface, Target("oauth2_server")],
) -> None:
    billing = Client("Billing", "billing", await anyio.to_thread.run_sync(hasher.hash, "s3cret"))
    _ = billing.set_grants(Grant("client_credentials")).set_scopes(Scope("invoices:read"))
    dashboard = Client("Dashboard", "dashboard", None)  # public: it holds no secret
    _ = dashboard.set_grants(Grant("authorization_code"), Grant("refresh_token"))
    _ = dashboard.set_redirect_uris(RedirectUri("https://dashboard.example.com/callback"))
    for client in (billing, dashboard):
        _ = client.set_active(True)
        await clients.save(client)
```

- Store the *hash* of a secret, made with the hasher under `Target("oauth2_server")`; a client
  registered with secret `None` is public and must send a proof key.
- A client with no grants may use any; with no scopes it is given `scopes.default` when saved.
- `set_active(False)` and a save (or `update-client --deactivate`) stops a client: it is refused
  as `invalid_client` wherever it names itself, holding a secret or not.
- With a database store use the commands instead: `oauth2-server:create-client NAME
  [IDENTIFIER] [SECRET] --grant-type … --scope … --redirect-uri … [--public]` prints the secret
  once; `update-client`, `delete-client`, `list-clients` administer; `clear-expired-tokens` is the
  one to schedule.

## Serve the device verification page

```python
from fastapi import FastAPI
from xtr_dependency_injection import Injected
from xtr_security import Security
from xtr_security_oauth2_server.manager.device_code_manager_interface import (
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer

app = FastAPI()


@app.post("/device")  # behind the sign-in firewall, and rate limited
async def approve_device(
    user_code: str,
    approved: bool,
    device_codes: Injected[DeviceCodeManagerInterface],
    server: Injected[AuthorizationServer],
    security: Injected[Security],
) -> dict[str, str]:
    found = await device_codes.find_by_user_code(user_code)
    user = security.get_user()
    if found is None or user is None:
        return {"status": "unknown code"}
    await server.complete_device_authorization_request(
        found.get_identifier(), user.get_user_identifier(), approved
    )
    return {"status": "recorded"}
```

Name the page as `device_code_verification_uri`. A user code is 8 characters of 20, so limit how
often the page may be guessed at (xtr-http-kernel's `RateLimited`).

## Build the servers by hand

The core needs no container: `AuthorizationServer(client_repository, access_token_repository,
scope_repository, signer, encryption_key, encryption_key_type, dispatcher, response_type=None)`,
then `enable_grant_type(ClientCredentialsGrant(dispatcher, clock), ttl)`, and
`await server.respond_to_access_token_request(request, response)` with
`xtr-http-message-contracts` messages. `ResourceServer(access_tokens,
BearerTokenValidator(access_tokens, jws_provider, issuer, clock))` reads a token back. The
runnable whole is the core README's Quick start; grants, extra claims, a response type of your
own and an add-on bundle: [references/extending.md](references/extending.md).

## Testing

Serve the application over ASGI inside its own lifespan; nothing is mocked. The kernel reads the
keys from the environment, so a test mints them:

```python
import base64
import secrets

import httpx
import pytest
from xtr_security_jwt.services.key_loader import generate_signing_key

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_a_service_is_issued_a_token(tmp_path, monkeypatch) -> None:
    key = tmp_path / "oauth2.pem"
    _ = key.write_text(generate_signing_key("RS256").as_pem(private=True).decode())
    monkeypatch.setenv("OAUTH2_SERVER_PRIVATE_KEY_PATH", str(key))
    monkeypatch.setenv("JWT_SECRET_KEY_PATH", str(key))  # the sign-in firewall's key
    monkeypatch.setenv(
        "OAUTH2_SERVER_ENCRYPTION_KEY",
        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="),
    )
    from main import app  # builds the kernel and calls setup(app, kernel)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as http:
            issued = await http.post(
                "/token",
                data={"grant_type": "client_credentials", "scope": "invoices:read"},
                auth=("billing", "s3cret"),
            )
            token = issued.json()["access_token"]
            called = await http.get("/api/invoices", headers={"Authorization": f"Bearer {token}"})

    assert called.json() == {"caller": "billing"}
```

- `InMemoryPersistenceConfig()` is the test store: each kernel starts empty.
- Send cookies as a `Cookie` header, not per-request `cookies=`.
- Test a listener, a grant or a repository bridge with no kernel: they are plain objects.
- `await assert_zero_config(OAuth2ServerBundle)` from `xtr_dependency_injection.testing` holds:
  the bundle boots unconfigured.

## Use in an application

1. **Install** — `uv add xtr-security-oauth2-server`. With xtr-orm installed beside it, clients
   and credentials can live in a database; install xtr-console beside it for the commands.
2. **Recipe** — `uv run xtr-recipes recipes:sync` lists `OAuth2ServerBundle`, writes
   `<app>/config/oauth2_server.py`, `OAUTH2_SERVER_PRIVATE_KEY_PATH` and a commented-out
   `OAUTH2_SERVER_ENCRYPTION_KEY` in `.env`, adds `/secrets/*.pem` to `.gitignore`, and writes
   `<app>/config/routes/oauth2_server.py`. It prints the rest: the keys, the issuer, `setup`, the
   three firewalls, the consent listener, a client, the scheduled sweep, the revision.
3. **Activate** — `OAuth2ServerBundle: {"all": True}` in `BUNDLES` (and `JwtBundle` when the end
   user signs in with a self-issued token); an unbound `Firewall()` on the application,
   `Kernel(..., concurrent_scoped_access=True)` and `setup(app, kernel)`, which adds the
   endpoints.
4. **Brings along** — the security, clock, event-dispatcher and HTTP-kernel bundles always; the
   logging and console bundles when installed.
5. **Configure** — `issuer`, `private_key`, `encryption_key`, `scopes.available`, `persistence` in
   `<app>/config/oauth2_server.py`; the three firewalls in `<app>/config/security.py`; a listener
   on `OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE`.
6. **Environment** — `OAUTH2_SERVER_PRIVATE_KEY_PATH` (the signing key's file) and
   `OAUTH2_SERVER_ENCRYPTION_KEY` (base64url of 32 random bytes). Read when a server is built,
   never at build.
7. **Ignore** — `/secrets/*.pem`.
8. **Remove** — `uv run xtr-recipes recipes:remove xtr-security-oauth2-server`, then undo the
   printed steps: router, firewalls, listener, clients.
9. **Check** — `debug:bundles` shows `oauth2_server` active; `debug:config oauth2_server`;
   `GET /.well-known/oauth-authorization-server`; `list oauth2-server` names six commands.

## Errors

All derive from `OAuth2Error`.

| Error | Raised when |
| --- | --- |
| `OAuthServerError` | A protocol refusal; the endpoints answer it. By hand, `await error.generate_http_response(response)` |
| `InvalidConfigurationError` (`xtr_security_oauth2_server.exception`) | A setting unusable or missing where a service needs it — named, with `<app>/config/oauth2_server.py` |
| `ClientAlreadyRegisteredError` | Registering an identifier already taken |
| `OAuth2AuthenticationFailedError` (`xtr_security_oauth2_server.security.exception`) | The API's firewall refused a token: `401`, `invalid_token` |
| `InvalidArgumentError` (`xtr_security_oauth2_server_core.exception`) | A library object used wrongly — a reserved extra claim, an unreadable key |

## Do not

- Do not name an issuer with a path, or try to prefix `oauth2_server_well_known` (refused):
  RFC 8414 places the description under the issuer. Prefix `oauth2_server` instead.
- Do not `app.include_router(...)` these endpoints yourself: `setup` adds them.
- Do not put a firewall in front of `/token`, `/revoke`, `/introspect` or `/device-code`: the
  server authenticates the client there.
- Do not approve every authorization request in a listener for third-party clients; show a page
  and protect its form against cross-site posts.
- Do not store a client secret in plaintext, or compare one with `==`.
- Do not reuse the `JwtBundle` key: this server's key loader lives under `Target("oauth2_server")`.
- Do not mint keys at runtime or commit them; mount the deployment's own.
- Do not use `InMemoryPersistenceConfig()` in a deployment of more than one process.
- Do not turn `persist_access_token` off if access tokens must be revocable before they expire.
