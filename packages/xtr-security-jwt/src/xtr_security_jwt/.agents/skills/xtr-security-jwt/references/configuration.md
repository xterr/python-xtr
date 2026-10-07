# JwtConfig, field by field

`from xtr_security_jwt.bundle import JwtConfig`. A frozen dataclass; every field has a default,
but the bundle refuses to build without `secret_key` and `issuer`.

| Field | Default | What it is |
| --- | --- | --- |
| `secret_key` | `None` | **Required.** The private key or shared secret, as key text or a file path |
| `issuer` | `""` | **Required.** The `iss` every token is stamped with and checked against |
| `audience` | `()` | Audiences a token is minted for; when set, a presented token's `aud` must name at least one. Always a tuple — `audience="api"` is refused, write `audience=("api",)` |
| `public_key` | `None` | The verifying key, or `None` to derive it from the private key |
| `additional_public_keys` | `()` | Files of extra public keys a token may also verify against, each named after the key id it holds |
| `pass_phrase` | `""` | The pass phrase the private key is encrypted with |
| `token_ttl` | `3600` | Seconds a minted token lives; must be positive |
| `allow_no_expiration` | `False` | Whether a token with no `exp` is honoured |
| `clock_skew` | `0` | Seconds of skew tolerated on a verified token's time claims; must not be negative |
| `encoder` | `EncoderConfig()` | How a token is signed |
| `user_id_claim` | `"username"` | The claim the identifier is written into and read back from |
| `token_extractors` | `TokenExtractorsConfig()` | Where a firewall reads a token from |

A bad combination raises `InvalidArgumentError` (from `xtr_security_core.exception`) as the
config is built: a negative `clock_skew`, a `token_ttl` of zero or less, an empty
`user_id_claim`, a string `audience`, or a `TokenExtractorsConfig` with every extractor off.

## Key material

`secret_key` and `public_key` each take either the key text itself or the path of a file holding
it. An existing file wins, so a key that happens to look like a path is still read from disk
when that path exists. `additional_public_keys` must each be a readable **file**: they are other
issuers' keys a deployment trusts.

Every key file is named after the key it holds, the way `jwt:generate-keypair` writes it —
`<kid>.pem` and `<kid>.jwks.json` — so the file's name is the id a presented token's `kid`
header names that key by, and a token naming one is verified in a single attempt. A key given
as text names no id, and a JWK or JWK set carries its own `kid`, which wins over the file name.
An extra file that cannot be read as a key of the configured algorithm's type is refused by
name: a key a deployment named is meant to be trusted, so it is never quietly dropped.

With `HS256`, `HS384` or `HS512` the build measures the secret the key loader resolves — the
file's contents when `secret_key` names one, the string itself otherwise — and refuses anything
under 32, 48 or 64 bytes with `InvalidConfigurationError`.

Point the key at a file through the environment rather than embedding it:

```python
JwtConfig(secret_key=env("file:JWT_SECRET_KEY_PATH"), pass_phrase=env("JWT_PASSPHRASE"))
```

The placeholder is resolved at boot, not at build, so the file need not exist while compiling.

## Algorithm

`EncoderConfig(service=None, signature_algorithm="RS256")`. `service` names a registered encoder
to sign with instead of the default joserfc one.

| Family | Algorithms | Key |
| --- | --- | --- |
| RSA | `RS256`, `RS384`, `RS512`, `PS256`, `PS384`, `PS512` | An RSA key pair |
| Elliptic curve | `ES256`, `ES384`, `ES512` | An EC key pair |
| Edwards curve | `EdDSA` | An OKP key pair |
| Shared secret | `HS256`, `HS384`, `HS512` | One secret; `secret_key` is it, and there is no pair |

Anything else raises `InvalidArgumentError`, naming the allowed set.

## Token extractors

`TokenExtractorsConfig` groups the four places a firewall may read a token from. All four
configs import from `xtr_security_jwt.bundle`.

| Config | Default | Reads |
| --- | --- | --- |
| `AuthorizationHeaderExtractorConfig(enabled=True, prefix="Bearer", name="Authorization")` | on | A header value, after the scheme prefix. An empty `prefix` takes the whole value |
| `CookieExtractorConfig(enabled=False, name="BEARER")` | off | A named cookie |
| `QueryParameterExtractorConfig(enabled=False, name="bearer")` | off | A named query parameter |
| `SplitCookieExtractorConfig(enabled=False, cookies=())` | off | Several named cookies, rejoined in the order given |

```python
from xtr_security_jwt.bundle import CookieExtractorConfig, JwtConfig, TokenExtractorsConfig

JwtConfig(
    secret_key=...,
    token_extractors=TokenExtractorsConfig(
        cookie=CookieExtractorConfig(enabled=True, name="access_token"),
    ),
)
```

Enabling more than one means a token is accepted from any of them, first match winning.
Disabling all four is refused as the configuration is built: a firewall must read a token from
somewhere.
