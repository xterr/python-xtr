# Extending the server

Everything here uses the bundle's own extension points — a tag, a prepended configuration, a
response type the container builds. Never inject the container, and never patch the shipped
grants.

## A grant of the application's own

A class subclassing the core's `GrantTypeInterface` — `AbstractGrant` will do — and registered as
a service is tagged `GRANT_TAG` by autoconfiguration and enabled on the server, issuing for
`authorization_server.access_token_ttl`. Its inherited constructor takes the dispatcher and the
clock.

```python
from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_security_oauth2_server_core.grant.abstract_grant import AbstractGrant

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )


@final
@as_service  # nominally a grant: tagged, collected and enabled with no more wiring
class ServiceAccountGrant(AbstractGrant):
    @override
    def get_identifier(self) -> str:
        return "urn:example:params:oauth:grant-type:service_account"

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        client = await self.validate_client(request)
        scopes = await self.validate_scopes(self.get_request_parameter("scope", request))
        access_token = await self.issue_access_token(access_token_ttl, client, None, scopes)
        response_type.set_access_token(access_token)
        return response_type
```

- Two grants answering one identifier fail the first build of the server, naming both: turn the
  shipped one off with its `enable_*` setting to replace it.
- A grant needing constructor arguments of its own, or a lifetime of its own, is registered by a
  bundle: `services.set(MyGrant).set_argument(...).add_tag(GRANT_TAG, access_token_ttl=...)`.
- The description's `grant_types_supported` names every grant the server runs, this one included.

## An add-on bundle

An add-on (an identity layer, say) requires `OAuth2ServerBundle`; the server bundle never knows
it exists. This is the shape the package's own add-on test drives:

```python
from dataclasses import replace
from datetime import timedelta

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle, required_bundle
from xtr_security_oauth2_server.bundle import (
    GRANT_TAG,
    METADATA_TAG,
    OAuth2ServerBundle,
    OAuth2ServerConfig,
)


@required_bundle(OAuth2ServerBundle)
@as_bundle("nonce_extension")
class ExtensionBundle(Bundle):
    @override
    def prepend_extension(self, builder) -> None:
        builder.prepend_extension_config(OAuth2ServerConfig, _extended)

    @override
    def load_extension(self, config, services, builder) -> None:
        server = builder.get_extension_config(OAuth2ServerConfig).authorization_server
        _ = services.set(NonceStamp)
        _ = (
            services.set(NonceAuthCodeGrant)
            .set_argument("auth_code_ttl", server.auth_code_ttl)
            .set_argument("refresh_token_ttl", server.refresh_token_ttl)
            .set_argument(
                "require_code_challenge", server.require_code_challenge_for_public_clients
            )
            .add_tag(GRANT_TAG, access_token_ttl=timedelta(minutes=3))
        )
        _ = services.set(NonceMetadataContributor).add_tag(METADATA_TAG)


def _extended(config: OAuth2ServerConfig) -> OAuth2ServerConfig:
    return replace(
        config,
        authorization_server=replace(
            config.authorization_server,
            enable_auth_code_grant=False,  # one identifier, one flow
            response_type_class=NonceTokenResponse,
        ),
    )
```

- A tagged grant is handed none of the settings the bundle gives the built-in ones, so it reads
  the lifetimes and the proof-key requirement off `get_extension_config` and sets them itself.
- A prepended configuration loses to the application's own `@configure` functions.
- The description is read off the grants the server runs, so with `enable_auth_code_grant=False`
  and the `AuthCodeGrant` subclass in its place it still names `authorization_code`, the
  `authorization_endpoint` and the `code` response type.

### Carry a parameter through the authorization code

Subclass `AuthCodeGrant` (the one shipped grant that is not final) and use its seams:

| Seam | Use |
| --- | --- |
| `create_authorization_request()` | Return an `AuthorizationRequest` subclass carrying the extra parameter across consent |
| `validate_authorization_request(request)` | Call `super()`, then read `self.get_query_string_parameter(name, request)` onto it |
| `get_auth_code_payload(auth_code, authorization_request)` | Call `super()` and add to the dictionary; the caller seals it into the code |
| `respond_to_access_token_request(request, response_type, ttl)` | Call `super()`, then read the code back with `self.decrypt(self.get_request_parameter("code", request))` and hand what it carried to the response type |

The constructor is `AuthCodeGrant(dispatcher, clock, auth_code_repository,
refresh_token_repository, auth_code_ttl)`; call `set_refresh_token_ttl(...)` and
`disable_require_code_challenge_for_public_clients()` as the deployment's settings say.

### A response type of its own

```python
from collections.abc import Mapping

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
    AccessTokenEntityInterface,
)
from xtr_security_oauth2_server_core.response_types.bearer_token_response import BearerTokenResponse


class NonceTokenResponse(BearerTokenResponse):
    def __init__(self, clock: ClockInterface, stamp: NonceStamp) -> None:
        super().__init__(clock)
        self._stamp = stamp
        self._nonce: str | None = None

    def set_nonce(self, nonce: str | None) -> None:
        self._nonce = nonce

    @override
    def get_extra_params(self, access_token: AccessTokenEntityInterface) -> Mapping[str, object]:
        return {} if self._nonce is None else {"nonce_handshake": self._stamp.stamp(self._nonce)}
```

Named as `response_type_class`, it is registered as a service, so its constructor may take
services, and each request is answered on a shallow copy — per-request state set on it never
reaches another request. Import the names its constructor reads at module level: the container
reads them at runtime.

### A field in the description

```python
from collections.abc import Mapping

from typing_extensions import override
from xtr_security_oauth2_server.metadata_contributor_interface import MetadataContributorInterface


class NonceMetadataContributor(MetadataContributorInterface):
    @override
    def get_metadata(self) -> Mapping[str, object]:
        return {"nonce_parameter_supported": True}
```

Tagged `METADATA_TAG` (attribute `priority`, an int, default 0; the higher wins a field two
contributors publish). A contribution never replaces a field the server publishes itself.

### A route of its own

Ship a route resource — a plain function declared `@as_route_resource("my_addon")` from
`xtr_http_kernel.routing.decorator`, filling an `APIRouter` with native routes, scanned by the
add-on's bundle with `services.load(...)`. The application's routes files register it —
`app.include_router(resources["my_addon"])`; routing is never imported automatically — and the
application's firewall decides who reaches it: `OAuth2AuthenticatorConfig()` on that path
accepts this server's access tokens.

## The core by hand

With no container at all, build the servers from constructors — the core README's Quick start is
the runnable whole: entities from the traits (the interface last among the bases), the
repositories, an `AccessTokenSigner(jws_provider, key_id, issuer, clock)`, then
`AuthorizationServer(...)` and `enable_grant_type(grant, ttl)`. `TokenServer(client_repository,
access_token_repository, refresh_token_repository, jws_provider, issuer, encryption_key,
encryption_key_type, dispatcher, clock)` answers revocation and introspection.
