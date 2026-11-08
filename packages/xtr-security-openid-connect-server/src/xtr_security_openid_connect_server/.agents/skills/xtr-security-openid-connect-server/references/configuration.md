# Configuration

Everything the OpenID Connect provider reads, where it is written, and what it refuses.

## `OpenIdConnectServerConfig`

Written in `<app>/config/packages/openid_connect_server.py`, returned from a `@configure`
function. Frozen, and buildable with no arguments: the bundle builds and boots on these defaults.

| Field | Type | Default | What it does |
|---|---|---|---|
| `identity_provider` | `type[IdentityProviderInterface] \| None` | `None` | The application's class that finds a signed-in end-user and the claims they hold. The bundle registers it and aliases it under `IdentityProviderInterface` |
| `claim_sets` | `Mapping[str, tuple[str, ...]]` | `{}` | The claims a scope of the application's own reveals, by scope |
| `id_token_ttl` | `timedelta \| None` | `None` | How long an ID token lasts. `None` has it expire with the access token answered beside it |
| `login_path` | `str` | `"/login"` | Where an end-user asked to sign in again is sent |
| `login_firewall` | `str` | `"main"` | The firewall signing them in there, whose session keeps the request to return to |
| `authorize_path` | `str` | `"/authorize"` | Where this deployment serves the authorization endpoint, which is where the prompt step acts |

### What it refuses, at build

`__post_init__` raises `InvalidConfigurationError`, naming the setting and this file, when:

- `login_path`, `login_firewall` or `authorize_path` is the empty string;
- `id_token_ttl` is set and not positive, which would mint ID tokens already expired;
- `claim_sets` holds a set for the empty scope;
- `claim_sets` holds a set for `profile`, `email`, `address` or `phone` — the four scopes OpenID
  Connect Core defines together with the claims they reveal. Give those claims a scope of the
  application's own instead.

### What it reports later, by name

- `identity_provider` unset: the provider still builds, boots and runs the console. The first
  request to `/userinfo` raises `InvalidConfigurationError` naming the setting and the file.
- A stateless `login_firewall`: raised the first time a re-login is asked of it, naming
  `stateless`, the firewall, `<app>/config/packages/security.py` and `login_firewall`.

## The authorization server's settings this package reads

Written in `<app>/config/packages/oauth2_server.py`, on `AuthorizationServerConfig`.

| Setting | Read for |
|---|---|
| `issuer` | The `iss` every ID token claims, and the origin the document's `userinfo_endpoint` is built on. Never the request's `Host`. Unconfigured, `userinfo_endpoint` is left out |
| `signature_algorithm` | The ID token's `alg`, the digest `at_hash` is taken with (for `EdDSA`, the one the server key's curve signs with: SHA-512 over Ed25519, SHAKE256 over Ed448), and the one entry in `id_token_signing_alg_values_supported` |
| `auth_code_ttl`, `refresh_token_ttl`, `require_code_challenge_for_public_clients` | Handed to this package's flow, which the server hands no settings of its own |
| `scopes.available` | `openid` is appended when the tuple names anything and lacks it. An empty tuple stays empty, so the authorization server's own error about it still fires |

## The three settings this bundle puts in place

`prepend_extension` sets them; `process` fails the build when the resolved configuration does not
carry them, because an application `@configure` transform runs after a bundle's prepend.

| Setting | Made | Why |
|---|---|---|
| `enable_auth_code_grant` | `False` | This package registers the flow answering `authorization_code`; two grants for one type are refused |
| `response_type_class` | `IdTokenResponse` | The plain bearer answer cannot carry an `id_token`. A subclass of it is accepted |
| `enable_metadata_endpoint` | left `True` | Without the description there is nothing for a client to discover the provider from |

Each refusal names the setting, says this bundle set it, and points at
`<app>/config/packages/oauth2_server.py`.

## Claim sets

`ClaimExtractor` holds the protocol's four, then whatever `claim_sets` adds, in the order given.
`extract(scopes, claims)` keeps only the names a granted scope's set holds **and** the user holds;
a later scope wins a name two sets both hold.

| Scope | Claims it reveals |
|---|---|
| `profile` | `name`, `family_name`, `given_name`, `middle_name`, `nickname`, `preferred_username`, `profile`, `picture`, `website`, `gender`, `birthdate`, `zoneinfo`, `locale`, `updated_at` |
| `email` | `email`, `email_verified` |
| `address` | `address` |
| `phone` | `phone_number`, `phone_number_verified` |

`openid` itself has no set, and reveals nothing. Build sets by hand with
`ClaimSetEntity(scope, claim_names)`, or bring a class of your own meeting
`ClaimSetEntityInterface`.

## The published document

`OpenIdMetadataContributor` adds these to the authorization server's description, answered both at
`/.well-known/openid-configuration` and at the server's own
`/.well-known/oauth-authorization-server`.

| Field | Value |
|---|---|
| `userinfo_endpoint` | `issuer` plus the path this application mounts the endpoint at, read on every call, so a routes file that moved it publishes where it now is. Left out with no issuer, or outside a served request |
| `subject_types_supported` | `["public"]` |
| `id_token_signing_alg_values_supported` | `[signature_algorithm]` — one entry, because there is one key |
| `claims_supported` | Sorted: `sub`, `iss`, `aud`, `exp`, `iat`, `auth_time`, `nonce`, and every claim **name** of every claim set. Never a scope name |
| `claims_parameter_supported`, `request_parameter_supported`, `request_uri_parameter_supported` | `False` |

A deployment on the authorization server's `RS256` default publishes `RS256`, which is what
Discovery 1.0 § 3 asks of the document. One configured for another algorithm publishes only that
one.
