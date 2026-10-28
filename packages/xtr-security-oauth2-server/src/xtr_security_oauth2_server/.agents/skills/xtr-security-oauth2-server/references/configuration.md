# OAuth2ServerConfig, field by field

`from xtr_security_oauth2_server.bundle import ...`. Frozen dataclasses, each buildable with no
arguments; a value of the wrong shape (an issuer with a path, a lifetime that is not positive, a
default scope that is not available, an empty role prefix) raises `InvalidConfigurationError` as
the configuration is built. A setting that is merely **missing** is reported later, by the first
service that needs it, naming the setting and `<app>/config/packages/oauth2_server.py`:

| Missing | Reported when |
| --- | --- |
| `authorization_server.private_key` | anything signs: a token is issued, the key set is published |
| `authorization_server.encryption_key` | the authorization or token server is built |
| `authorization_server.issuer` | a token is signed or read, or the description is served |
| `scopes.available` | the scope manager or the description is built |
| `persistence` | any store is asked for |
| `authorization_server.device_code_verification_uri` | the device grant is built — on by default |

## `OAuth2ServerConfig`

| Field | Default | What it is |
| --- | --- | --- |
| `authorization_server` | `AuthorizationServerConfig()` | What signs, seals, issues and runs |
| `resource_server` | `ResourceServerConfig()` | How tokens are verified |
| `scopes` | `ScopesConfig()` | The vocabulary of scopes |
| `persistence` | `None` | `InMemoryPersistenceConfig()`, `OrmPersistenceConfig(...)` or `CustomPersistenceConfig(...)` |
| `client` | `ClientConfig()` | `classname`: the client class, a subclass of `AbstractClient` (default `Client`) |
| `role_prefix` | `"ROLE_OAUTH2_"` | Scope `invoices:read` becomes role `ROLE_OAUTH2_INVOICES:READ`; never empty |

## `AuthorizationServerConfig`

| Field | Default | What it is |
| --- | --- | --- |
| `issuer` | `None` | An origin — scheme and host, no path, query or fragment |
| `private_key` | `None` | PEM text or a file path; `env("resolve:OAUTH2_SERVER_PRIVATE_KEY_PATH")` |
| `private_key_passphrase` | `""` | Its pass phrase |
| `encryption_key` | `None` | Seals codes and refresh tokens |
| `encryption_key_type` | `"plain"` | `"plain"`: a password of 32+ characters, stretched once (PBKDF2-HMAC-SHA256). `"key"`: base64url of 32 random bytes |
| `audience` | `None` | `aud` of every access token, and required by the resource server; `None` addresses a token to its client and checks nothing |
| `signature_algorithm` | `"RS256"` | `RS*`, `PS*`, `ES*`, `EdDSA` |
| `additional_public_keys` | `()` | Files of further keys tokens verify against, and the key set publishes |
| `access_token_ttl` | `timedelta(hours=1)` | Built-in grants issue for this; a tagged grant may carry its own |
| `refresh_token_ttl` | `timedelta(days=30)` | |
| `auth_code_ttl` | `timedelta(minutes=10)` | |
| `device_code_ttl` | `timedelta(minutes=10)` | |
| `enable_client_credentials_grant` | `True` | |
| `enable_auth_code_grant` | `True` | |
| `enable_refresh_token_grant` | `True` | |
| `enable_device_code_grant` | `True` | Needs `device_code_verification_uri` |
| `enable_password_grant` | `False` | Answers through `OAuth2Events.USER_RESOLVE` |
| `enable_implicit_grant` | `False` | |
| `require_code_challenge_for_public_clients` | `True` | |
| `persist_access_token` | `True` | Off: no access-token store, nothing revocable before expiry |
| `revoke_refresh_tokens` | `True` | A redeemed refresh token is spent (rotation) |
| `response_type_class` | `None` | A `ResponseTypeInterface` class the container builds; `BearerTokenResponse` otherwise |
| `device_code_verification_uri` | `""` | The application's page for the user code |
| `enable_device_code_verification_uri_complete_generation` | `True` | |
| `device_code_polling_interval` | `5` | Seconds; not negative |
| `enable_device_code_polling_interval_visibility` | `True` | |
| `enable_revocation_endpoint` | `True` | `404` when off |
| `enable_introspection_endpoint` | `False` | `404` when off |
| `enable_metadata_endpoint` | `True` | `404` when off |

## `ResourceServerConfig` and `ScopesConfig`

| Field | Default | What it is |
| --- | --- | --- |
| `ResourceServerConfig.public_key` | `None` | The verifying key; derived from `private_key` when `None` — set it for an API running apart from the server |
| `ResourceServerConfig.jwt_leeway` | `None` | A `timedelta` widening a token's window; not negative |
| `ScopesConfig.available` | `()` | Every scope a client may ask for; empty is reported as missing |
| `ScopesConfig.default` | `()` | Given to a client registered with no scopes (the `PRE_SAVE_CLIENT` listener); within `available`; may be empty |

A token request naming no scope is granted the client's registered scopes; a client with no
scopes may ask for any.

## Changing one environment

```python
from dataclasses import replace

from xtr_dependency_injection import configure, when
from xtr_security_oauth2_server.bundle import OAuth2ServerConfig


@configure
@when("prod")
def introspection_in_production(config: OAuth2ServerConfig) -> OAuth2ServerConfig:
    return replace(
        config,
        authorization_server=replace(
            config.authorization_server, enable_introspection_endpoint=True
        ),
    )
```

## Keys

- `oauth2-server:generate-keypair [ALGORITHM]` writes the file `private_key` names (and
  `resource_server.public_key`'s, when set); `--dry-run` prints, `--skip-if-exists` and
  `--overwrite` decide about a file in place. It refuses when `private_key` is key text or unset.
- The encryption key is minted by hand:
  `python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='))"`.
- This server's `RawKeyLoader` and `JoserfcJwsProvider` are registered under
  `Target("oauth2_server")`, never the bare interfaces `JwtBundle` owns. Rotate by adding the old
  public key under `additional_public_keys` before swapping `private_key`.
