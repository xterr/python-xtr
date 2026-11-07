<div align="center">

# xtr-security-openid-connect-server

**OpenID Connect for the xtr OAuth 2.0 authorization server.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

[xtr-security-oauth2-server](../xtr-security-oauth2-server) issues access tokens: a client that
holds one may act for somebody, and learns nothing about who that somebody is. "Sign in with this
server" is the other half, and this package is it — an add-on bundle that turns that server into
an OpenID Connect provider for the authorization code flow, without changing how the server works.

- 🪪 **An ID token** — the token answer to a sign-in carries a signed `id_token` naming the
  end-user: `iss`, `sub`, `aud`, `exp`, `iat`, `auth_time`, the `nonce` the client sent, and an
  `at_hash` binding the access token answered beside it.
- 👤 **`/userinfo`** — `GET` and `POST`; answers the subject plus the claims the token's scopes
  reveal, from the application's own users, and fails closed.
- 🔎 **`/.well-known/openid-configuration`** — one document: the authorization server's own
  description, with the provider's fields contributed to it.
- 🔁 **`prompt` and `max_age`** — `none` answers `login_required` rather than showing a page,
  `login` and an expired `max_age` send the end-user back through the login page and return to the
  request, `consent` is read by the application's consent listener.
- 🔑 **One key, one key set** — the ID token is signed with the authorization server's own signer
  and `kid`, so a client verifies it from the `/.well-known/jwks.json` that server already
  publishes.

It follows OpenID Connect Core 1.0 and Discovery 1.0 for the authorization code flow, checked by
`tests/conformance/`, whose README lists every requirement, every deliberate deviation and the
optional manual run of the OpenID Foundation suite. Running that suite is not a claim this
repository makes.

Out of scope on purpose: no logout of any kind, no implicit or hybrid flow, no pairwise subjects,
no `claims` parameter, no request objects, no dynamic client registration, and no ID token on a
refresh.

## Install

```sh
uv add xtr-security-openid-connect-server     # the provider, its bundle and its endpoints
```

Requires Python 3.11+. It brings [xtr-security-oauth2-server](../xtr-security-oauth2-server) and
its protocol library along, with the security family, the key layer, the clock, the event
dispatcher and the HTTP kernel.

## Quick start

A deployment whose authorization server already runs the code flow, signing end-users in.

### 1. List both bundles

```python
# app/config/bundles.py
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_openid_connect_server.bundle import OpenIdConnectServerBundle

BUNDLES = {OAuth2ServerBundle: {"all": True}, OpenIdConnectServerBundle: {"all": True}}
```

Listing the provider alone is enough: it requires the authorization server's bundle. The provider
puts its own flow and token answer in place of the shipped ones, and adds `openid` to
`scopes.available` when that tuple names anything at all.

### 2. Say where the users are

```python
# app/identity_provider.py
from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_core.exception import UserNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )

    from xtr_security_openid_connect_server.entities import UserClaimsEntityInterface


@final
class Person:
    """A resource owner the server knows by identifier, with the claims they hold."""

    def __init__(self, identifier: str, claims: Mapping[str, object]) -> None:
        self._identifier = identifier
        self._claims = claims

    def get_identifier(self) -> str:
        return self._identifier

    async def get_claims(self) -> Mapping[str, object]:
        return self._claims


@final
class PeopleIdentityProvider:
    """Finds the end-user a token names, and the claims that describe them."""

    async def get_user_entity_by_identifier(
        self,
        identifier: str,
        client: ClientEntityInterface,
    ) -> UserClaimsEntityInterface:
        del client  # Every client is told the same about a person here.
        if identifier != "alice":
            raise UserNotFoundError(identifier)
        return Person(
            "alice",
            {"name": "Alice", "email": "alice@example.com", "email_verified": True},
        )
```

```python
# app/config/packages/openid_connect_server.py
from xtr_dependency_injection import configure
from xtr_security_openid_connect_server.bundle import OpenIdConnectServerConfig

from app.identity_provider import PeopleIdentityProvider

__all__ = ["openid_connect_server"]


@configure
def openid_connect_server() -> OpenIdConnectServerConfig:
    return OpenIdConnectServerConfig(
        identity_provider=PeopleIdentityProvider,
        login_path="/login",
        login_firewall="main",
    )
```

The bundle registers the class named here, so the container builds it from its constructor. Do not
register it a second time.

### 3. Serve the endpoints and guard them

```python
# app/config/routes/openid_connect_server.py
from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI

__all__ = ["openid_connect_server"]


@as_routes
def openid_connect_server(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    app.include_router(resources["openid_connect_server"])
    app.include_router(resources["openid_connect_server_well_known"])
```

```python
# app/config/packages/security.py — the two firewalls this package needs
from xtr_dependency_injection import configure
from xtr_security.bundle import FirewallConfig, SecurityConfig
from xtr_security_jwt.bundle import JwtAuthenticatorConfig
from xtr_security_oauth2_server.bundle import OAuth2AuthenticatorConfig
from xtr_security_openid_connect_server.bundle import PROMPT_LISTENER

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    return SecurityConfig(
        providers={"people": ...},
        firewalls={
            "main": FirewallConfig(
                pattern=r"^/(authorize|login)",
                stateless=False,
                provider="people",
                authenticators=(JwtAuthenticatorConfig(),),
                listeners=(PROMPT_LISTENER,),
            ),
            "userinfo": FirewallConfig(
                pattern=r"^/userinfo",
                provider="people",
                authenticators=(OAuth2AuthenticatorConfig(),),
            ),
        },
    )
```

`PROMPT_LISTENER` is the qualifier of the step that decides `prompt` and `max_age`. Only the
application knows which firewall signs end-users in, so only it can list the step there — and that
firewall must keep a session, because the authorization request waits in it while the end-user
signs in again.

### 4. Sign in

```console
$ # the client sends the browser to:
$ #   /authorize?response_type=code&client_id=dashboard&redirect_uri=https://dashboard.example.com/callback
$ #            &scope=openid%20profile%20email&state=xyz&nonce=n-0S6_WzA2Mj&code_challenge=…&code_challenge_method=S256
$ curl -s -u dashboard:s3cret -d grant_type=authorization_code -d code=… \
       -d redirect_uri=https://dashboard.example.com/callback -d code_verifier=… \
       https://authorization.example.com/token
{"token_type":"Bearer","expires_in":3600,"access_token":"ey…","refresh_token":"def…","id_token":"ey…"}

$ curl -s -H "Authorization: Bearer ey…" https://authorization.example.com/userinfo
{"sub":"alice","name":"Alice","email":"alice@example.com","email_verified":true}
```

## Configure

`<app>/config/packages/openid_connect_server.py` returns an `OpenIdConnectServerConfig`. Every
field has a default, so the bundle builds and boots with no configuration at all.

| Field | Default | What it does |
|---|---|---|
| `identity_provider` | `None` | The application's class implementing `IdentityProviderInterface`. The bundle registers it. Unset, the provider still boots; `/userinfo` reports the setting by name |
| `claim_sets` | `{}` | The claims a scope of the application's own reveals, by scope — `{"company": ("company_id",)}`. One of the protocol's four scopes is refused |
| `id_token_ttl` | `None` | How long an ID token lasts. `None` has it expire with the access token answered beside it |
| `login_path` | `"/login"` | Where an end-user asked to sign in again is sent |
| `login_firewall` | `"main"` | The firewall signing them in there, whose session keeps the request to return to |
| `authorize_path` | `"/authorize"` | Where this deployment serves the authorization endpoint, which is where the prompt step acts |

The authorization server's own settings decide the rest, in
`<app>/config/packages/oauth2_server.py`: `authorization_server.issuer` is the `iss` every ID token
claims (never the request's `Host`), and `authorization_server.signature_algorithm` is what the ID
token is signed with — the same key, signer and `kid` as an access token.

Three settings of that server this bundle puts in place itself, and refuses to be undone:
`enable_auth_code_grant=False` (this package registers the flow answering that grant type),
`response_type_class=IdTokenResponse`, and `enable_metadata_endpoint` left on. An application
`@configure` transform runs after a bundle's prepend, so one changing any of them fails the build
with a message naming the setting.

The four claim sets OpenID Connect Core defines ship held and cannot be changed: `profile`,
`email`, `address` and `phone`. An end-user granting `email` agrees to share what `email` means,
and a set redefining it would hand a client other claims under the name they agreed to. Add the
scopes a deployment answers for to `scopes.available`, or `/authorize` refuses a client asking for
them.

## Endpoints

Two route resources, registered by `<app>/config/routes/openid_connect_server.py`:

| Resource | Route | Path | Methods |
|---|---|---|---|
| `openid_connect_server` | `openid_connect_server_userinfo` | `/userinfo` | `GET`, `POST` |
| `openid_connect_server_well_known` | `openid_connect_server_configuration` | `/.well-known/openid-configuration` | `GET` |

- **`/userinfo`** reads no credential of its own: it answers from the token the request's firewall
  settled on, which is why it fails closed — with no firewall in front of it, there is no token and
  every request is refused. A token that is not one of this server's, or one a client was issued
  for itself, is `401 invalid_token`; one not granted `openid` is `403 insufficient_scope`; each
  carries an RFC 6750 `Bearer` challenge. A success is `200`, `application/json`,
  `cache-control: no-store`, `{"sub": …, **claims}` — `sub` first and never replaced by a claim of
  the identity provider's. A `POST` carries a form-encoded body or none; anything else is
  `400 invalid_request`. The access token is read from the `Authorization` header only.
- **`/.well-known/openid-configuration`** answers the authorization server's description with the
  provider's fields contributed to it: `userinfo_endpoint` (the issuer plus the path this
  application mounts the endpoint at, so moving it under a prefix moves the published URL),
  `subject_types_supported: ["public"]`, `id_token_signing_alg_values_supported`,
  `claims_supported` (claim names, never scope names), and `claims_parameter_supported`,
  `request_parameter_supported` and `request_uri_parameter_supported`, all `false`. The
  authorization server's own `/.well-known/oauth-authorization-server` carries the same fields: it
  is one description, answered at two paths. The resource is kept apart from the movable one
  because Discovery 1.0 fixes the document at that path under the issuer.
- **`/authorize`** and **`/token`** stay the authorization server's own endpoints. This package
  changes what happens behind them: the authorization endpoint answers `GET` and a posted form, a
  request asking for `openid` must name its `redirect_uri` (a request without it still may leave it
  out, as OAuth 2.0 allows a client registered with one URI), `prompt=select_account` is refused
  rather than ignored, and the token answer to a sign-in carries the `id_token`. A refresh never
  does.

A deployment that keeps the authorization server's `RS256` default publishes `RS256` as its ID
token signature algorithm, which is what Discovery 1.0 § 3 requires of the document and Core § 15.1
of the provider. A deployment configured for another `signature_algorithm` publishes only that one:
the ID token is signed with the authorization server's key, and there is one of those.

## Services

`OpenIdConnectServerBundle` registers, under the types an application injects:

| Service | Lifetime | What it does |
|---|---|---|
| `ClaimExtractor` | shared | Holds every claim set — the protocol's four, then the application's — and picks the claims a token's scopes reveal out of a user's |
| `IdTokenSettings` | shared | What an ID token is signed with and how long it lasts, read off the authorization server's settings |
| `IdentityProviderInterface` | shared | The class `identity_provider` names. Unset, a stand-in raises `InvalidConfigurationError` naming the setting the first time a user is needed |
| `OpenIdAuthCodeGrant` | shared, tagged `GRANT_TAG` | The code flow carrying the sign-in: it seals the `nonce` and the sign-in time into the code, and hands them to the token answer when it is redeemed |
| `UserInfoController` | per request | Answers `/userinfo`, over the request's own token storage |
| `OpenIdMetadataContributor` | shared, tagged `METADATA_TAG` | The provider's fields of the description |
| `OpenIdPromptListener` | per request, qualifier `openid_connect_server#prompt_listener` | The firewall chain step deciding `prompt` and `max_age`, also aliased under `FirewallListenerInterface` |

`IdTokenResponse` is not registered here: the authorization server registers whichever class its
`response_type_class` names, which this bundle made this one. Inject the prompt step by the
qualifier `PROMPT_LISTENER` carries, never by building it: it takes the request's token storage.

The library stands on its own — `ClaimExtractor`, `ClaimSetEntity`, `token_hash`, `parse_prompt`,
`consent_required`, `IdTokenResponse` and `OpenIdAuthCodeGrant` are plain objects, built from their
constructors — and the bundle is the integration on top.

## Events

This package hears and raises nothing of its own: it uses the authorization server's events.

| Name | Listener | Priority |
|---|---|---|
| `OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE` | `stamp_auth_time` records on the request when the end-user last signed in, from the newest proof on the firewall's token, and decides nothing | `AUTH_TIME_LISTENER_PRIORITY`, `2048` |

A consent listener of the application's runs **below** that priority — the default `0` does —
because resolving a request stops the listeners after it, and the sign-in time has to be recorded
first. Read what the client asked for through `OpenIdAuthorizationRequest.get_prompt()`:

```python
from xtr_event_dispatcher import as_event_listener
from xtr_security_oauth2_server.event.authorization_request_resolve_event import (
    AuthorizationRequestResolveEvent,
)
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_openid_connect_server.prompt import consent_required
from xtr_security_openid_connect_server.request_types.open_id_authorization_request import (
    OpenIdAuthorizationRequest,
)


@as_event_listener(OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE)
async def ask_for_consent(event: AuthorizationRequestResolveEvent) -> None:
    request = event.get_authorization_request()
    asked = request.get_prompt() if isinstance(request, OpenIdAuthorizationRequest) else frozenset()
    if "none" in asked and not consent_already_given(event):
        # No page may be shown, so the client is told instead.
        raise consent_required(event)
    if "consent" in asked or not consent_already_given(event):
        _ = event.set_response(await consent_page(event))
        return
    _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)
```

`consent_required(event)` builds the refusal, delivered to the validated redirect URI with the
`state` echoed back. A remembered sign-in that proved no credential leaves the sign-in time
unknown: the ID token then states none, and a `max_age` request treats it as stale.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what removing
it undoes.

- **Install** — `uv add xtr-security-openid-connect-server`, beside an application already hosting
  [xtr-security-oauth2-server](../xtr-security-oauth2-server).
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* and *Configure* steps below,
  and no other: it lists `OpenIdConnectServerBundle`, writes a starting
  `config/packages/openid_connect_server.py` with the login page, login firewall and authorization
  path, and writes `config/routes/openid_connect_server.py` serving the userinfo endpoint at its
  default path and the configuration document at the root. It prints what a recipe cannot make for
  you: the identity provider class, listing the prompt step in the login firewall's `listeners`,
  the firewall in front of `/userinfo`, the scopes, the issuer, and the consent listener.
- **Activate** — `OpenIdConnectServerBundle: {"all": True}` in `BUNDLES` in
  `<app>/config/bundles.py`, imported from `xtr_security_openid_connect_server.bundle`. The
  authorization server's own `setup(app, kernel)` and `concurrent_scoped_access=True` already
  apply; this package adds no step there.
- **Brings along** — the [OAuth 2.0 authorization server](../xtr-security-oauth2-server) and,
  through it and on its own account, the [security bundle](../xtr-security), the
  [clock](../xtr-clock), the [event dispatcher](../xtr-event-dispatcher) and the
  [HTTP kernel](../xtr-http-kernel), because this bundle requires every one of them.
- **Configure** — with no configuration the bundle builds and boots, and answers no claims: a
  `config/packages/openid_connect_server.py` `@configure` function returning an
  `OpenIdConnectServerConfig` names the `identity_provider`, and the login page and firewall a
  re-login goes through — see [Configure](#configure). In
  `<app>/config/packages/security.py`, list `openid_connect_server#prompt_listener` in the
  `listeners` of that firewall and leave it stateful, and put a firewall carrying
  `OAuth2AuthenticatorConfig()` in front of `/userinfo`. In
  `<app>/config/packages/oauth2_server.py`, name the issuer and add the claim scopes this
  deployment answers for to `scopes.available`. A listener on
  `OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE`, below `AUTH_TIME_LISTENER_PRIORITY`, answers the
  consent question — see [Events](#events). `config/routes/openid_connect_server.py` registers both
  route resources; move the userinfo endpoint there, and leave the document at the root — see
  [Endpoints](#endpoints).
- **Environment** — nothing of its own. The ID token is signed with the authorization server's key,
  so that server's `OAUTH2_SERVER_PRIVATE_KEY_PATH` and its two other variables are all there are.
- **Ignore** — nothing: this package writes no file into the project.
- **Remove** — `uv run xtr-recipes recipes:remove xtr-security-openid-connect-server`, then undo
  the steps it printed: the identity provider, the prompt step in the firewall's `listeners`, the
  userinfo firewall and the consent listener are the application's own. The authorization server
  goes back to its shipped code flow and bearer answer by itself, both having been this bundle's
  to prepend.
- **Check** — `debug:bundles` lists `openid_connect_server` as active, with `oauth2_server` among
  the bundles it requires; `debug:config openid_connect_server` shows the resolved identity
  provider, claim sets, ID-token lifetime, login page and firewall; and
  `GET /.well-known/openid-configuration` answers with this provider's description, naming the
  issuer and the userinfo endpoint.

## Kernel / bundle

```python
# app/config/bundles.py
from xtr_security_openid_connect_server.bundle import OpenIdConnectServerBundle

BUNDLES = {OpenIdConnectServerBundle: {"all": True}}
```

`OpenIdConnectServerBundle` (name `openid_connect_server`, config `OpenIdConnectServerConfig`)
requires the [OAuth 2.0 authorization server](../xtr-security-oauth2-server),
[security](../xtr-security), [clock](../xtr-clock), [event dispatcher](../xtr-event-dispatcher) and
[HTTP kernel](../xtr-http-kernel) bundles, so listing it alone brings every one of them along. No
other bundle requires it, so it only arrives by being listed. It:

- prepends onto the authorization server's configuration the flow and the answer a sign-in takes —
  `enable_auth_code_grant=False`, `response_type_class=IdTokenResponse` — and appends `openid` to
  `scopes.available` when that tuple names anything, leaving an empty one empty so the
  authorization server's own error about it still fires;
- registers the claim sets, the ID-token settings, the identity provider, the flow tagged
  `GRANT_TAG`, the userinfo controller and its route resources, the metadata contributor tagged
  `METADATA_TAG`, and the prompt step under `openid_connect_server#prompt_listener`;
- loads the listener recording the sign-in time on the authorization server's consent event;
- fails the build when the resolved authorization server runs the shipped redirect flow, answers
  with something that cannot carry an ID token, or does not describe itself — each named, because
  an application transform runs after this bundle's prepend and can undo it.

The authorization server knows nothing of this bundle: everything above goes through seams it
publishes for an add-on. It reads no key, user or issuer while building, so it builds and boots
with no configuration.

## Errors

Everything this package raises derives from `OpenIdConnectServerError`, itself an `OAuth2Error`
(`xtr_security_oauth2_server_core.exception`), so one `except OAuth2Error` still catches the
authorization server and its identity layer together:

| Error | Base | Raised when |
|---|---|---|
| `OpenIdConnectServerError` | `OAuth2Error` | The base of them all; nothing raises it directly |
| `InvalidConfigurationError` | `OpenIdConnectServerError`, `ValueError` | A setting the provider cannot run with, or one missing where a service needs it — `identity_provider` unset, a login firewall that keeps no session — naming it and `<app>/config/packages/openid_connect_server.py` |
| `InvalidArgumentError` | `OpenIdConnectServerError`, `ValueError` | One of this package's objects used wrongly: a claim set naming no scope, a negative `max_age`, a claim set for a scope the protocol defines, an unsigned ID token back from the signature provider |
| `UnsupportedAlgorithmError` | `OpenIdConnectServerError` | A signature algorithm whose digest its name does not say, so no `at_hash` can be taken for it |

A refusal a client is owed is never one of these: it is the authorization server's `OAuthServerError`,
which the endpoints deliver. `parse_prompt` raises it as `invalid_request`, `login_required` and
`consent_required` build it for the two refusals a sign-in can end in, and the flow raises
`server_error` when the token answer cannot carry an ID token.

## Layout

```
xtr_security_openid_connect_server/
├── _endpoint_paths.py          where each endpoint lives by default, and its route name
├── routing/                    the endpoints, and the two route resources routes files register
├── controller/                 UserInfoController
├── grant/                      OpenIdAuthCodeGrant
├── request_types/              OpenIdAuthorizationRequest: nonce, prompt, max_age, auth_time
├── response_types/             IdTokenResponse
├── firewall/                   OpenIdPromptListener
├── event_listener/             the listener recording the sign-in time, and its priority
├── repositories/               IdentityProviderInterface
├── entities/                   the claim set, and what a user with claims answers to
├── claim_extractor.py          the claim sets, and picking a user's claims through them
├── id_token_settings.py        what an ID token is signed with, and how long it lasts
├── token_hash.py               at_hash
├── prompt.py                   parse_prompt, login_required, consent_required
├── open_id_metadata_contributor.py  the provider's fields of the description
├── exception/                  OpenIdConnectServerError and the three under it
├── recipe/                     what recipes:sync applies
└── bundle/                     OpenIdConnectServerBundle, its configuration and PROMPT_LISTENER
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-security-openid-connect-server`; run the commands below from there. The conformance
suite, one module per part of the protocol, is under
[`tests/conformance/`](tests/conformance/README.md).

```sh
uv sync --all-packages --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest --cov
```

## License

MIT — see [LICENSE](LICENSE).
