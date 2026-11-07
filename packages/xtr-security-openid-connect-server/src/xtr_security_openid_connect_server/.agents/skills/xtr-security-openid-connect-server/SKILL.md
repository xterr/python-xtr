---
name: xtr-security-openid-connect-server
description: How to turn an xtr-security-oauth2-server deployment into an OpenID Connect provider for the authorization code flow with xtr-security-openid-connect-server - ID tokens with nonce, auth_time and at_hash, a /userinfo endpoint, the /.well-known/openid-configuration document, and prompt and max_age handling. Use when an application must offer "sign in with" to its OAuth clients, issue or debug an id_token, answer claims for a signed-in end user, write an IdentityProviderInterface, add the claims a scope reveals, decide prompt=none, prompt=login, prompt=consent or max_age, send an end user back through the login page and return to the authorization request, publish or read the OpenID configuration document, raise consent_required from a consent listener, or fix an InvalidConfigurationError naming identity_provider, login_firewall or a claim set.
---

# xtr-security-openid-connect-server

An add-on bundle on [xtr-security-oauth2-server](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security-oauth2-server):
it makes that deployment's authorization server an OpenID Connect provider for the authorization
code flow. A client asking for the `openid` scope is answered an `id_token` naming the end-user,
reads that end-user's claims from `/userinfo`, and discovers both from
`/.well-known/openid-configuration`.

The authorization server knows nothing of this package: the flows, clients, endpoints, consent
event and `oauth2` firewall key are the `xtr-security-oauth2-server` skill's; firewalls, voters and
user providers are the `xtr-security` skill's. This skill covers only the identity layer on top.

No logout, no implicit or hybrid flow, no pairwise subjects, no `claims` parameter, no request
objects, no dynamic client registration, no `id_token` on a refresh.

## Quick reference

- List `OpenIdConnectServerBundle` beside `OAuth2ServerBundle`; it requires that bundle, so listing
  it alone brings it along. It puts `enable_auth_code_grant=False` and
  `response_type_class=IdTokenResponse` in place, and appends `openid` to `scopes.available` when
  that tuple names anything.
- Write a class implementing `IdentityProviderInterface` (async
  `get_user_entity_by_identifier(identifier, client)`) and name it in `identity_provider`. The
  bundle registers it; never register it again.
- List `PROMPT_LISTENER` (`"openid_connect_server#prompt_listener"`, from
  `xtr_security_openid_connect_server.bundle`) in the `listeners` of the firewall that signs
  end-users in, and leave that firewall stateful.
- Put a firewall carrying `OAuth2AuthenticatorConfig()` in front of `/userinfo`. The endpoint reads
  no credential of its own, so without one every request is refused.
- Two route resources: `openid_connect_server` (`/userinfo`, `GET` and `POST`) moves under a
  prefix; `openid_connect_server_well_known` (`/.well-known/openid-configuration`) stays at the
  root.
- The ID token claims `iss`, `sub`, `aud`, `exp`, `iat`, `auth_time`, `nonce` and `at_hash` — no
  scope claims. `profile`, `email`, `address` and `phone` are answered by `/userinfo` only.
- The ID token is signed with the authorization server's key, `kid` and
  `authorization_server.signature_algorithm`, so the published key set verifies it.
- A consent listener runs below `AUTH_TIME_LISTENER_PRIORITY` (`2048`) and raises
  `consent_required(event)` when `prompt=none` needs a consent not yet given.
- Every error derives from `OpenIdConnectServerError`, itself an `OAuth2Error`.

## Configure the provider

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
        claim_sets={"company": ("company_id",)},
        login_path="/login",
        login_firewall="main",
    )
```

- Every field has a default, so the bundle builds and boots with nothing written. `/userinfo` is
  what reports an unset `identity_provider`, by name and with this file.
- `claim_sets` adds the claims a scope of the application's own reveals. The four scopes OpenID
  Connect Core defines come held and are refused here.
- Add the claim scopes the deployment answers for to `scopes.available` in
  `app/config/packages/oauth2_server.py`, or `/authorize` refuses a client asking for them.

Every field, default and refusal:
[references/configuration.md](references/configuration.md).

## Say where the end-users are

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
    def __init__(self, identifier: str, claims: Mapping[str, object]) -> None:
        self._identifier = identifier
        self._claims = claims

    def get_identifier(self) -> str:
        return self._identifier

    async def get_claims(self) -> Mapping[str, object]:
        return self._claims


@final
class PeopleIdentityProvider:
    async def get_user_entity_by_identifier(
        self,
        identifier: str,
        client: ClientEntityInterface,
    ) -> UserClaimsEntityInterface:
        del client  # Describe a person differently per client here, if a deployment must.
        if identifier != "alice":
            raise UserNotFoundError(identifier)
        return Person("alice", {"name": "Alice", "email": "alice@example.com"})
```

- The identifier comes from a token this server issued, so a missing user raises
  `UserNotFoundError` rather than answering `None` — the error the security family's user providers
  already raise, so an implementation built on one lets it through unchanged.
- Claims the granted scopes do not reveal are dropped by `ClaimExtractor`, so returning everything
  a person holds is safe.
- The container builds the class from its constructor: declare what it needs as typed parameters.

## Serve and guard the endpoints

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
from xtr_security.bundle import FirewallConfig
from xtr_security_oauth2_server.bundle import OAuth2AuthenticatorConfig
from xtr_security_openid_connect_server.bundle import PROMPT_LISTENER

main = FirewallConfig(
    pattern=r"^/(authorize|login)",
    stateless=False,
    provider="people",
    authenticators=(...,),  # whatever signs an end-user in
    listeners=(PROMPT_LISTENER,),
)
userinfo = FirewallConfig(
    pattern=r"^/userinfo",
    provider="people",
    authenticators=(OAuth2AuthenticatorConfig(),),
)
```

- The prompt step must sit on the firewall that signs end-users in, the one `login_firewall` names:
  only that firewall covers both the authorization endpoint and the login page, and the
  authorization request waits in its session during a re-login. A stateless one is refused by name
  the first time a re-login is asked of it.
- Moving the userinfo endpoint under a prefix moves the `userinfo_endpoint` the document publishes;
  move the firewall pattern with it.

## Decide prompt, max_age and consent

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


@as_event_listener(OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE)  # priority 0, below 2048
async def ask_for_consent(event: AuthorizationRequestResolveEvent) -> None:
    request = event.get_authorization_request()
    asked = request.get_prompt() if isinstance(request, OpenIdAuthorizationRequest) else frozenset()
    if "none" in asked and not consent_already_given(event):
        raise consent_required(event)
    if "consent" in asked or not consent_already_given(event):
        _ = event.set_response(await consent_page(event))
        return
    _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)
```

- `prompt=none` with nobody signed in, or a sign-in older than `max_age`, is answered
  `login_required` at the validated redirect URI with the `state` echoed — decided by the prompt
  step, before the endpoint refuses an anonymous request.
- `prompt=login`, or an exceeded `max_age`, parks the request in the session and redirects to
  `login_path`; the return trip carries the same request with `login` taken out of `prompt`.
- A remembered sign-in proves no credential, so the sign-in time is unknown: the ID token states no
  `auth_time`, and any `max_age` treats it as stale.
- `prompt=select_account` and an unknown value are `invalid_request`, never ignored.

What each parameter does to a round trip, and what the ID token then carries:
[references/flows.md](references/flows.md).

## Testing

Serve the application over ASGI inside its own lifespan, both bundles listed, with
`InMemoryPersistenceConfig()` so each kernel starts empty. Nothing is mocked.

```python
import httpx
import pytest
from xtr_dependency_injection.testing import assert_zero_config
from xtr_security_openid_connect_server.bundle import OpenIdConnectServerBundle

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_the_bundle_boots_unconfigured() -> None:
    await assert_zero_config(OpenIdConnectServerBundle)


async def test_a_sign_in_is_answered_an_id_token(app) -> None:  # app calls setup(app, kernel)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as http:
            answered = await http.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "…",
                    "redirect_uri": "https://dashboard.example.com/callback",
                    "code_verifier": "…",
                },
                auth=("dashboard", "s3cret"),
            )

    assert "id_token" in answered.json()
```

- Check the `id_token` with a client implementation, not by re-signing it: the provider's own suite
  reads it with `xtr-security-http`'s OpenID Connect client, which shares no code with it.
- `ClaimExtractor`, `ClaimSetEntity`, `token_hash`, `parse_prompt`, `consent_required`,
  `IdTokenResponse` and `OpenIdAuthCodeGrant` are plain objects: test them with no kernel.
- Freeze time with `MockClock` from [xtr-clock](https://github.com/xterr/python-xtr/tree/main/packages/xtr-clock)
  wherever `auth_time`, `max_age` or an expiry is asserted.

## Use in an application

1. **Install** — `uv add xtr-security-openid-connect-server`, beside an application already hosting
   `xtr-security-oauth2-server`.
2. **Recipe** — `uv run xtr-recipes recipes:sync` lists `OpenIdConnectServerBundle`, writes a
   starting `config/packages/openid_connect_server.py` and a
   `config/routes/openid_connect_server.py` serving the userinfo endpoint at its default path and
   the document at the root. It prints the rest: the identity provider, the prompt step, the
   userinfo firewall, the scopes, the issuer, the consent listener.
3. **Activate** — `OpenIdConnectServerBundle: {"all": True}` in `BUNDLES` in
   `<app>/config/bundles.py`. The authorization server's `setup(app, kernel)` and
   `concurrent_scoped_access=True` already apply.
4. **Brings along** — the OAuth 2.0 authorization server, and the security, clock, event-dispatcher
   and HTTP-kernel bundles, all required.
5. **Configure** — `identity_provider`, `login_path` and `login_firewall` in
   `config/packages/openid_connect_server.py`; `openid_connect_server#prompt_listener` in that
   firewall's `listeners`, a firewall over `/userinfo`, in
   `config/packages/security.py`; the issuer and the claim scopes in
   `config/packages/oauth2_server.py`; a consent listener below `AUTH_TIME_LISTENER_PRIORITY`.
6. **Environment** — nothing of its own: the ID token is signed with the authorization server's
   key, so that server's variables are all there are.
7. **Ignore** — nothing: this package writes no file into the project.
8. **Remove** — `uv run xtr-recipes recipes:remove xtr-security-openid-connect-server`, then undo
   the printed steps. The authorization server goes back to its shipped code flow and bearer answer
   by itself.
9. **Check** — `debug:bundles` shows `openid_connect_server` active with `oauth2_server` required;
   `debug:config openid_connect_server`; `GET /.well-known/openid-configuration` names the issuer
   and the userinfo endpoint.

## Errors

All derive from `OpenIdConnectServerError`, itself an `OAuth2Error`.

| Error | Raised when |
| --- | --- |
| `InvalidConfigurationError` | A setting the provider cannot run with, or one missing where a service needs it — `identity_provider` unset, a stateless `login_firewall`, an authorization server whose flow or answer was changed back — named, with the file to write it in |
| `InvalidArgumentError` | One of this package's objects used wrongly: a claim set naming no scope or one the protocol defines, a negative `max_age`, an unsigned ID token back from the signature provider |
| `UnsupportedAlgorithmError` | A signature algorithm whose digest its name does not say, so no `at_hash` can be taken for it |

A refusal a client is owed is the authorization server's `OAuthServerError`, which the endpoints
deliver: `invalid_request` from `parse_prompt` and a malformed `max_age` or missing `redirect_uri`,
`login_required` and `consent_required` for the two refusals a sign-in can end in, and
`server_error` when the token answer cannot carry an ID token.

## Do not

- Do not register the `identity_provider` class yourself, or alias it under
  `IdentityProviderInterface`: the bundle does both from the setting.
- Do not serve `/userinfo` without a firewall carrying `OAuth2AuthenticatorConfig()`, and do not
  send its token in the request body: the header is the only place it is read.
- Do not list the prompt step on a stateless firewall, or on one that does not cover the login page
  as well as the authorization endpoint.
- Do not change `enable_auth_code_grant`, `response_type_class` or `enable_metadata_endpoint` in an
  application `@configure`: a transform runs after this bundle's prepend, and the build is failed
  by name.
- Do not expect scope claims in the ID token — `name`, `email`, `address`, `phone_number` are
  `/userinfo`'s — and do not expect an `id_token` from a refresh.
- Do not put a claim set under `profile`, `email`, `address` or `phone`: an end-user who granted one
  agreed to what the protocol says it reveals.
- Do not register a consent listener at or above `AUTH_TIME_LISTENER_PRIORITY`: resolving a request
  stops the listeners after it, and the sign-in time would never be recorded.
- Do not try to move `/.well-known/openid-configuration` under a prefix: a client reads it at that
  path under the issuer.
- Do not claim certification. The OpenID Foundation suite is an optional manual run, described in
  the package's `tests/conformance/README.md`, and its outcome is nothing this package states.
