<div align="center">

# xtr-security-oauth2-server-core

**The OAuth 2.0 authorization-server library: grants, servers, entities, response types and the resource server.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

This is the framework-neutral half of [xtr-security-oauth2-server](../xtr-security-oauth2-server):
the authorization server, the token server, the grants, the entities and their interfaces, the
response types, the proof-key and redirect-URI validators, the resource server and the protocol
errors. An application builds them by hand, so nothing here reaches for a web framework, a
container or an ORM — it speaks the HTTP message contracts, and the caller hands it a request and
a response.

What it decides is the protocol; what it leaves to whoever builds it is storage. Every store is a
`Protocol` in `repositories/` — clients, scopes, access tokens, codes, refresh tokens, device
codes, users — with async methods, and every entity a store hands back is an interface in
`entities/`, composed from the traits in `entities/traits/`. Authorization codes and refresh
tokens are sealed (JWE `dir` + `A256GCM`), so storage only has to remember whether one was spent;
access tokens are signed RFC 9068 tokens, read back by the resource server without a round trip.

The bundle that wires all of this into an application on
[xtr-dependency-injection](../xtr-dependency-injection) — with stores, persistence, controllers,
a router, commands and a firewall authenticator — lives in
[xtr-security-oauth2-server](../xtr-security-oauth2-server), which depends on this package. To use
the server in an application, follow its
[Use in an application](../xtr-security-oauth2-server/README.md#use-in-an-application) section.

## Install

```sh
uv add xtr-security-oauth2-server-core
```

Most applications install [xtr-security-oauth2-server](../xtr-security-oauth2-server) instead,
which brings this along. Building the servers by hand also needs an event dispatcher and HTTP
messages: [xtr-event-dispatcher](../xtr-event-dispatcher) and
[xtr-http-message](../xtr-http-message) are what the Quick start uses.

## Quick start

An `AuthorizationServer` issuing a token to a service by client credentials, and a
`ResourceServer` reading it back — built from constructors, over stores written here in memory.

```python
import json
import secrets
from collections.abc import Sequence
from datetime import timedelta

import anyio
from xtr_clock import SystemClock
from xtr_event_dispatcher import EventDispatcher
from xtr_http_message import Response, ServerRequest
from xtr_security_jwt.services.jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.key_loader import RawKeyLoader, generate_signing_key, signing_key_id
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer
from xtr_security_oauth2_server_core.authorization_validators.bearer_token_validator import (
    BearerTokenValidator,
)
from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
    AccessTokenEntityInterface,
)
from xtr_security_oauth2_server_core.entities.access_token_signer import AccessTokenSigner
from xtr_security_oauth2_server_core.entities.client_entity_interface import ClientEntityInterface
from xtr_security_oauth2_server_core.entities.scope_entity_interface import ScopeEntityInterface
from xtr_security_oauth2_server_core.entities.traits.access_token_trait import AccessTokenTrait
from xtr_security_oauth2_server_core.entities.traits.client_trait import ClientTrait
from xtr_security_oauth2_server_core.entities.traits.entity_trait import EntityTrait
from xtr_security_oauth2_server_core.entities.traits.scope_trait import ScopeTrait
from xtr_security_oauth2_server_core.entities.traits.token_entity_trait import TokenEntityTrait
from xtr_security_oauth2_server_core.grant.client_credentials_grant import ClientCredentialsGrant
from xtr_security_oauth2_server_core.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.scope_repository_interface import (
    ScopeRepositoryInterface,
)
from xtr_security_oauth2_server_core.resource_server import ResourceServer

ISSUER = "https://authorization.example.com"


# Entities: the traits hold the state, the interface comes last.
class Client(EntityTrait, ClientTrait, ClientEntityInterface):
    def __init__(self, identifier: str, name: str) -> None:
        self.set_identifier(identifier)
        self._name = name
        self._redirect_uri = ()
        self._is_confidential = True


class Scope(EntityTrait, ScopeTrait, ScopeEntityInterface):
    def __init__(self, identifier: str) -> None:
        self.set_identifier(identifier)


class AccessToken(EntityTrait, TokenEntityTrait, AccessTokenTrait, AccessTokenEntityInterface):
    pass


# Repositories: where the server reads clients and scopes and keeps tokens.
class Clients(ClientRepositoryInterface):
    def __init__(self) -> None:
        self._clients = {"billing": (Client("billing", "Billing"), "billing-secret")}

    async def get_client_entity(self, client_identifier: str) -> ClientEntityInterface | None:
        found = self._clients.get(client_identifier)
        return found[0] if found is not None else None

    async def validate_client(
        self,
        client_identifier: str,
        client_secret: str | None,
        grant_type: str | None,
    ) -> bool:
        found = self._clients.get(client_identifier)
        # A real store keeps a hash and verifies it; never compare with ==.
        return found is not None and secrets.compare_digest(found[1], client_secret or "")


class Scopes(ScopeRepositoryInterface):
    async def get_scope_entity_by_identifier(self, identifier: str) -> ScopeEntityInterface | None:
        return Scope(identifier) if identifier in {"invoices:read", "invoices:write"} else None

    async def finalize_scopes(
        self,
        scopes: Sequence[ScopeEntityInterface],
        grant_type: str,
        client_entity: ClientEntityInterface,
        user_identifier: str | None = None,
        auth_code_id: str | None = None,
    ) -> Sequence[ScopeEntityInterface]:
        return scopes


class AccessTokens(AccessTokenRepositoryInterface):
    def __init__(self) -> None:
        self._revoked: set[str] = set()

    async def get_new_token(
        self,
        client_entity: ClientEntityInterface,
        scopes: Sequence[ScopeEntityInterface],
        user_identifier: str | None = None,
    ) -> AccessTokenEntityInterface:
        token = AccessToken()
        token.set_client(client_entity)
        for scope in scopes:
            token.add_scope(scope)
        if user_identifier is not None:
            token.set_user_identifier(user_identifier)
        return token

    async def persist_new_access_token(
        self, access_token_entity: AccessTokenEntityInterface
    ) -> None:
        pass  # keep it, so it can be revoked

    async def revoke_access_token(self, token_id: str) -> None:
        self._revoked.add(token_id)

    async def is_access_token_revoked(self, token_id: str) -> bool:
        return token_id in self._revoked


async def main() -> None:
    clock = SystemClock()
    dispatcher = EventDispatcher()
    key_loader = RawKeyLoader(generate_signing_key("RS256").as_pem(private=True).decode(), None)
    jws_provider = JoserfcJwsProvider(key_loader, "RS256", None, 0, clock)
    signer = AccessTokenSigner(
        jws_provider,
        signing_key_id(key_loader, "RS256"),  # the kid the published key set names
        ISSUER,
        clock,
    )
    encryption_key = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"  # base64url of 32 bytes
    clients, scopes, access_tokens = Clients(), Scopes(), AccessTokens()

    server = AuthorizationServer(
        clients, access_tokens, scopes, signer, encryption_key, "key", dispatcher
    )
    server.enable_grant_type(ClientCredentialsGrant(dispatcher, clock), timedelta(minutes=15))

    # The token endpoint: the caller hands in the request and the response to answer on.
    request = ServerRequest("POST", f"{ISSUER}/token").with_parsed_body(
        {
            "grant_type": "client_credentials",
            "client_id": "billing",
            "client_secret": "billing-secret",
            "scope": "invoices:read",
        },
    )
    answer = await server.respond_to_access_token_request(request, Response())
    issued = json.loads(await answer.get_body().get_contents())
    print(answer.get_status_code(), issued["token_type"], issued["expires_in"])

    # The API: the resource server reads the bearer token back.
    resource_server = ResourceServer(
        access_tokens,
        BearerTokenValidator(access_tokens, jws_provider, ISSUER, clock),
    )
    call = ServerRequest(
        "GET",
        "https://api.example.com/invoices",
        {"Authorization": f"Bearer {issued['access_token']}"},
    )
    read = await resource_server.validate_authenticated_request(call)
    print(read.get_attribute("oauth_client_id"), read.get_attribute("oauth_scopes"))


anyio.run(main)
```

```console
200 Bearer 899
billing ['invoices:read']
```

- A refusal is an `OAuthServerError`: catch it around a server call and answer with
  `await error.generate_http_response(response)`. Every answer here writes a body, so every
  `generate_http_response` is awaited.
- The entities compose traits with the interface **last** among the bases: an interface listed
  first would shadow the traits' accessors with its own empty stubs.
- `encryption_key_type` is `"key"` (the base64url of 32 random bytes) or `"plain"` (a password of
  at least 32 characters, stretched once with PBKDF2 when the server is built).

## Grants

Each grant takes the event dispatcher and the clock, plus the stores only it needs; the server
hands it the shared ones — client, access-token and scope repositories, the signer, the
encryption key — when `enable_grant_type(grant, access_token_ttl)` enables it.

| Grant | Identifier | Constructor |
|---|---|---|
| `ClientCredentialsGrant` | `client_credentials` | `(dispatcher, clock)` |
| `AuthCodeGrant` | `authorization_code` | `(dispatcher, clock, auth_code_repository, refresh_token_repository, auth_code_ttl)` |
| `RefreshTokenGrant` | `refresh_token` | `(dispatcher, clock, refresh_token_repository)` |
| `DeviceCodeGrant` | `urn:ietf:params:oauth:grant-type:device_code` | `(dispatcher, clock, device_code_repository, refresh_token_repository, device_code_ttl, verification_uri, retry_interval=5)` |
| `PasswordGrant` | `password` | `(dispatcher, clock, user_repository, refresh_token_repository)` |
| `ImplicitGrant` | `implicit` | `(dispatcher, clock, access_token_ttl, query_delimiter="#")` |

`OAuth2Grants` holds the identifiers. The authorization code grant requires a proof key of a
public client unless `disable_require_code_challenge_for_public_clients()` is called, refuses a
verifier for a code issued without a challenge, and judges the challenge by the method the code
carries. A grant of your own subclasses `AbstractGrant` (or `AbstractAuthorizeGrant` for one
reached through `/authorize`); `AuthCodeGrant` keeps two seams for one that carries something
through the code — `create_authorization_request()` and `get_auth_code_payload()`.

`AuthorizationServer` answers `validate_authorization_request` / `complete_authorization_request`,
`respond_to_access_token_request`, `respond_to_device_authorization_request` and
`complete_device_authorization_request(device_code, user_id, user_approved)`. `TokenServer`
answers `respond_to_token_revocation_request` (RFC 7009) and
`respond_to_token_introspection_request` (RFC 7662), with the same client authentication.

## Response types

| Response type | Answers |
|---|---|
| `BearerTokenResponse(clock)` | The token document: `token_type`, `expires_in`, `access_token`, `refresh_token`, `scope`. Override `get_extra_params(access_token)` to add fields |
| `DeviceCodeResponse(clock)` | `device_code`, `user_code`, `verification_uri`, `expires_in`, and the complete URI and interval when asked |
| `RedirectResponse()` | The redirect back to the client, carrying a code or, for the implicit grant, a token in the fragment |
| `IntrospectionResponse()` | `{"active": false}`, or the claims of a live token; `get_extra_params(token_type, token_data)` adds fields |

`AuthorizationServer`'s last argument is the `ResponseTypeInterface` it answers token requests
with — a `BearerTokenResponse` when left out. Each request is answered on a shallow copy, so the
services a response type holds are shared and per-request state is not.

## Events

The grants and servers announce through the dispatcher they were built with, each event under
its own name:

| Name | Event | When |
|---|---|---|
| `RequestEvent.ACCESS_TOKEN_ISSUED` | `RequestAccessTokenEvent` | An access token was issued |
| `RequestEvent.REFRESH_TOKEN_ISSUED` | `RequestRefreshTokenEvent` | A refresh token was issued |
| `RequestEvent.CLIENT_AUTHENTICATION_FAILED` | `RequestEvent` | A client could not be authenticated |
| `RequestEvent.USER_AUTHENTICATION_FAILED` | `RequestEvent` | The password grant refused a user's credentials |
| `RequestEvent.REFRESH_TOKEN_CLIENT_FAILED` | `RequestEvent` | A refresh token was presented by another client |

```python
from xtr_event_dispatcher import EventDispatcher
from xtr_security_oauth2_server_core.request_access_token_event import RequestAccessTokenEvent
from xtr_security_oauth2_server_core.request_event import RequestEvent


async def record(event: RequestAccessTokenEvent) -> None:
    print("issued", event.get_access_token().get_identifier())


dispatcher = EventDispatcher()
dispatcher.add_listener(RequestEvent.ACCESS_TOKEN_ISSUED, record)
```

## Errors

Everything the library raises derives from `OAuth2Error`
(`xtr_security_oauth2_server_core.exception`):

| Error | Base | Raised when |
|---|---|---|
| `OAuthServerError` | `OAuth2Error` | A request the protocol has a refusal for. Built by named constructors — `invalid_request`, `invalid_client`, `invalid_grant`, `invalid_scope`, `access_denied`, `unsupported_grant_type`, `slow_down`, … — and answered with `await generate_http_response(response, use_fragment=False)` |
| `UniqueTokenIdentifierConstraintViolationError` | `OAuthServerError` | A store met an identifier already taken; a grant retries ten times before it lets this out as a `500` |
| `InvalidArgumentError` | `OAuth2Error`, `ValueError` | One of the library's objects used wrongly — a reserved extra claim, an unreadable encryption key, a grant asked to work before it was enabled |

A refresh token that is invalid, expired or spent is `invalid_grant` with status `400`, as RFC
6749 §5.2 names it.

## Layout

```
xtr_security_oauth2_server_core/
├── authorization_server.py         AuthorizationServer
├── token_server.py                 TokenServer: revocation and introspection
├── resource_server.py              ResourceServer
├── abstract_handler.py             what grants and token handlers share
├── crypt_trait.py                  sealing codes and refresh tokens
├── oauth2_grants.py                the grant identifiers
├── bearer_challenge.py             the WWW-Authenticate challenge a bearer refusal carries
├── redirect_uri.py                 carrying parameters to where a browser is sent
├── request_event.py, request_access_token_event.py, request_refresh_token_event.py
├── grant/                          the grants and their interface
├── handlers/                       the revocation and introspection handlers
├── entities/                       the entity interfaces, AccessTokenSigner, traits/
├── repositories/                   the store interfaces
├── response_types/                 bearer, device code, redirect and introspection answers
├── request_types/                  AuthorizationRequest
├── authorization_validators/       BearerTokenValidator
├── code_challenge_verifiers/       S256 and plain
├── redirect_uri_validators/        exact matching, loopback ports aside
└── exception/                      OAuth2Error and the errors under it
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-security-oauth2-server-core`; run the commands below from there.

```sh
uv sync --all-packages --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest --cov
```

## License

MIT — see [LICENSE](LICENSE).
