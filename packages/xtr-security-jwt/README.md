<div align="center">

# xtr-security-jwt

**Self-issued JSON Web Tokens for xtr security: an encoder, a token manager and a firewall authenticator.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

The [security family](../xtr-security) verifies bearer tokens issued elsewhere, but issues none
of its own. This package is the self-issued-token layer on top of it: an application signs a
JSON Web Token for one of its users, hands it to a client, and accepts it back on a protected
route — the whole loop, with no authorization server.

It ships everything for both halves of that loop:

- 🔑 **A key loader** — a signing key given as text or a file path, an optional pass phrase, a
  public key derived from the private one when absent, and extra public keys other issuers are
  trusted by.
- ✍️ **An encoder and a token manager** — the encoder signs and verifies claims through a JWS
  provider; the token manager assembles the user's roles and identity, announces the claims for
  a listener to shape, signs them, and never reads any of the token from client input.
- 🔥 **A firewall key `jwt`** — one line in a firewall accepts self-issued tokens; the bundle
  wires the authenticator, the extractors and the user provider through the security family's
  seams.
- 🪪 **A stateless user** — a user rebuilt from a token's own claims, so a deployment that keeps
  no user store still authenticates a request by the token alone.
- 🛠️ **Commands** — mint a signing key pair, mint a token for a user, or check that the
  configured keys sign and verify.

## Install

```sh
uv add xtr-security-jwt              # the library and its JwtBundle
uv add "xtr-security-jwt[console]"   # + jwt:generate-keypair, jwt:generate-token, jwt:check-config
```

Requires Python 3.11+. The package ships a bundle, so it depends on the container and the
security bundle it wires into, alongside the security family's core and http edge and the event
dispatcher and clock — all come with it.

## Quick start

### 1. Mint a signing key

```console
$ jwt:generate-keypair --algorithm RS256 --output-dir secrets/
Wrote secrets/8f2c….pem and secrets/8f2c….jwks.json
```

The private PEM signs; the public JWK set verifies — publish it, keep the PEM secret.

### 2. Configure the signing key and a firewall

```python
# app/config/jwt.py
from xtr_dependency_injection import configure, env
from xtr_security_jwt.bundle import JwtConfig


@configure
def jwt() -> JwtConfig:
    return JwtConfig(
        secret_key=env("file:JWT_SECRET_KEY_PATH"),
        issuer=env("JWT_ISSUER"),
        user_id_claim="username",
    )
```

```python
# app/config/security.py
from xtr_dependency_injection import configure
from xtr_security.bundle import (
    AccessControlConfig,
    FirewallConfig,
    SecurityConfig,
)
from xtr_security_jwt.bundle import JwtAuthenticatorConfig, JwtUserProviderConfig


@configure
def security() -> SecurityConfig:
    return SecurityConfig(
        providers={"jwt_users": JwtUserProviderConfig()},
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="jwt_users",
                authenticators=(JwtAuthenticatorConfig(),),
            ),
        },
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
```

`JwtAuthenticatorConfig()` is the whole of what a firewall needs to accept self-issued tokens:
the keys, the algorithm and the extractors all come from the JWT bundle's own configuration.
`JwtUserProviderConfig()` is a stateless provider that rebuilds the user from the token's claims,
for a deployment that keeps no user store; a firewall with its own user provider names that
instead.

### 3. Protect the routes and write a `/token` endpoint

```python
# app/web.py
from typing import Annotated

from fastapi import FastAPI
from xtr_dependency_injection import Injected, Kernel
from xtr_http_kernel import setup
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser, Firewall
from xtr_security_jwt import JwtTokenManagerInterface

from app.bundles import BUNDLES

app = FastAPI(dependencies=[Firewall()])


@app.post("/token")
async def issue_token(
    identifier: str,
    tokens: Injected[JwtTokenManagerInterface],
) -> dict[str, str]:
    user = await _authenticated_user(identifier)  # the application checks the password
    return {"access_token": await tokens.create(user)}


@app.get("/api/me")
async def me(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, str]:
    return {"user": user.get_user_identifier()}


kernel = Kernel("app", concurrent_scoped_access=True)
setup(app, kernel)
```

The token manager assembles the registered claims and signs them; it never reads any of the
token from client input. The application authenticates the user before calling `create`, the
FastAPI-tutorial way — burning a dummy hash for an unknown user, and throttling the endpoint
with a `RateLimited` dependency.

```console
$ curl -i localhost:8000/api/me
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer

{"code":401,"message":"JWT Token not found"}

$ TOKEN=$(curl -s -X POST 'localhost:8000/token?identifier=ada' | jq -r .access_token)
$ curl -i -H "Authorization: Bearer $TOKEN" localhost:8000/api/me
HTTP/1.1 200 OK

{"user":"ada"}
```

## Configure

`JwtConfig` is a frozen dataclass buildable with no arguments, but the JWT bundle is an add-on
that cannot sign a token without a key: the build fails with an `InvalidConfigurationError`
naming the missing setting and the `<app>/config/jwt.py` `@configure` function when no
`secret_key` or no `issuer` is configured — it names both when both are missing.

An `env()` placeholder counts as configured: it stands for a variable read when the service
needing it is built, so it cannot decide anything while the container compiles. A
`secret_key=env(…)` too short for its HMAC algorithm, and an `issuer=env(…)` resolving to
nothing, are therefore refused where the key loader and the token manager are built, not at the
build.

| Field | Default | What it is |
|---|---|---|
| `secret_key` | `None` | The private key or shared secret that signs, as the key text or a file path. Required |
| `issuer` | `""` | The `iss` every token is stamped with and checked against. Required |
| `audience` | `()` | Audiences a token is minted for; when set, a presented token must name at least one. Always a tuple — `audience="api"` is refused, write `audience=("api",)` |
| `public_key` | `None` | The public key that verifies, or `None` to derive it from the private key |
| `additional_public_keys` | `()` | Files of extra public keys a token may also be verified against, each named after the key id it holds |
| `pass_phrase` | `""` | The pass phrase the private key is encrypted with |
| `token_ttl` | `3600` | How long a minted token lives, in seconds |
| `allow_no_expiration` | `False` | Whether a token with no expiry is honoured |
| `clock_skew` | `0` | Seconds of clock skew tolerated on a verified token's time claims |
| `encoder` | `EncoderConfig()` | The signature algorithm (`RS256` by default) and an optional encoder service override |
| `user_id_claim` | `"username"` | The claim the user's identifier is written into and read back from |
| `token_extractors` | `TokenExtractorsConfig()` | Where a firewall reads a token from |

A **token extractor** is one of four, told apart by where a token travels — the authorization
header is on by default, the others opt in:

| Extractor | Default | Reads |
|---|---|---|
| `authorization_header` | on, `Bearer` / `Authorization` | A token from a header, after a scheme prefix |
| `cookie` | off, `BEARER` | A token from a named cookie |
| `query_parameter` | off, `bearer` | A token from a named query parameter |
| `split_cookie` | off | A token split across several named cookies, rejoined |

A firewall authenticator is `JwtAuthenticatorConfig()` — it takes nothing: the keys, the
algorithm and the extractors all come from the JWT bundle's own configuration, and the user is
loaded through the firewall's own provider. A stateless user provider is
`JwtUserProviderConfig(user_class=JwtUser)` — the class the provider rebuilds from a token's
claims.

## Services

`JwtBundle` registers, from the signing key down:

| Service | Interface | What it does |
|---|---|---|
| `RawKeyLoader` | `KeyLoaderInterface` | Reads the signing and verifying key material |
| `JoserfcJwsProvider` | `JwsProviderInterface` | Signs a payload and verifies a token with joserfc |
| `DefaultJwtEncoder` | `JwtEncoderInterface` | Maps the provider's outcome to encode/decode failures |
| `JwtManager` | `JwtTokenManagerInterface` | Assembles, announces and signs a token, reads one back |

Every verifying key is imported once and filed under the id it is known by — the `kid` a JWK or
a JWK set carries, or the name of the file it was read from, since `jwt:generate-keypair` writes
`<kid>.pem` and `<kid>.jwks.json` — so a presented token naming a `kid` is verified in a single
attempt, and a deployment rotating keys keeps accepting tokens signed by the keys it still
trusts. An extra key file that cannot be read as a key of the configured algorithm's type is
refused by name rather than quietly dropped.

The token manager gathers every registered `PayloadEnrichmentInterface` into a chain, so a
deployment stamps a claim onto every token by registering an enrichment — a `RandomJtiEnrichment`
for a unique id — never by reaching for the container.

## Events

Every event is dispatched as itself, so a listener subscribes to the class it reads — the same
way the rest of the security family does:

| Event | Dispatched |
|---|---|
| `JwtCreatedEvent` | Before a token is signed; a listener may shape the claims and header |
| `JwtEncodedEvent` | After a token is signed |
| `JwtDecodedEvent` | After a token verifies; a listener may reject it |
| `JwtAuthenticatedEvent` | After a token authenticated a request |
| `JwtExpiredEvent` | When an expired token is refused |
| `JwtInvalidEvent` | When a bad token is refused |
| `JwtNotFoundEvent` | When a request carried no token |

Those seven are everything this package dispatches. The three refusals derive from
`AuthenticationFailureEvent`, which is never dispatched on its own, so a listener that handles
any refusal subscribes to that base — or to the `JwtFailureEventInterface` it implements —
rather than to all three.

## Commands

With the console extra and a console bundle active:

| Command | Does |
|---|---|
| `jwt:generate-keypair [--algorithm RS256\|ES256\|EdDSA] [--kid KID] [--output-dir DIR]` | Mints a signing key and prints its private PEM and public JWK set — or writes them to `DIR`, named by the key id |
| `jwt:generate-token IDENTIFIER [--provider NAME]` | Loads the user by identifier through a configured user provider and prints a token signed for it; `--provider` picks between several |
| `jwt:check-config` | Signs a probe token and reads it back, proving the configured keys sign and verify |

`jwt:generate-keypair` and `jwt:generate-token` print a private key and a usable access token to
standard output: run them only where the terminal, its scrollback and any shell history are
trusted, and prefer `--output-dir` for the key pair.

Writing with `--output-dir` leaves the private PEM `0o600`, the public JWK set `0o644`, and every
directory the command had to create `0o700`; a directory that already exists keeps the mode it
has. A key file already in place is not replaced unless `--force` is given, and a key is never
written through a symbolic link.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add xtr-security-jwt`; add `[console]` for the commands.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate*, *Configure*, *Environment*
  and *Ignore* steps below: it lists `JwtBundle`, writes a starting `<app>/config/jwt.py`,
  `JWT_SECRET_KEY_PATH` and `JWT_ISSUER` (both commented out) in `.env`, and adds `/secrets/*.pem`
  and `/secrets/*.jwks.json` to `.gitignore`. It prints the keypair and firewall steps, which a
  recipe cannot make for you.
- **Activate** — `JwtBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported from
  `xtr_security_jwt.bundle`. Then build the kernel with `concurrent_scoped_access=True` and call
  `setup(app, kernel)` where the application is served, as the security family requires.
- **Brings along** — the [security bundle](../xtr-security), the
  [clock](../xtr-clock) and the [event dispatcher](../xtr-event-dispatcher) always, because this
  bundle requires them; the [console](../xtr-console) bundle when xtr-console is installed, for
  the commands.
- **Configure** — the bundle needs a signing key and an issuer: a `<app>/config/jwt.py`
  `@configure` function returning a `JwtConfig(secret_key=…, issuer=…)`, and a firewall that lists
  `JwtAuthenticatorConfig()` under its `authenticators` — see [Configure](#configure) and
  [Kernel / bundle](#kernel--bundle). Without a `secret_key` or an `issuer` the build fails,
  naming the missing setting.
- **Environment** — whatever the key material reads: an application usually points the key at a
  file with `env("file:JWT_SECRET_KEY_PATH")`, so `JWT_SECRET_KEY_PATH` must be set; and
  `JWT_ISSUER`, the name every token is stamped with and checked against.
- **Ignore** — the key files the keypair command writes, when `--output-dir` points into the
  project: the recipe adds `/secrets/*.pem` and `/secrets/*.jwks.json` to `.gitignore` (or add
  wherever they land).
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/jwt.py` and the
  `JwtAuthenticatorConfig` from the firewall, then `uv remove xtr-security-jwt`.
- **Check** — `debug:bundles` shows `jwt` as `listed` and `active`, and `security` as `required`;
  `debug:firewall api` lists the firewall's `jwt` authenticator.

## Kernel / bundle

```python
# app/bundles.py
from xtr_security_jwt.bundle import JwtBundle

BUNDLES = {JwtBundle: {"all": True}}
```

`JwtBundle` registers the signing chain — the key loader, the JWS provider, the encoder and the
token manager — under their interfaces, and prepends onto the security configuration an
authenticator factory keyed `jwt` and a user-provider factory keyed `jwt`. A firewall's
`JwtAuthenticatorConfig` then builds a `JwtAuthenticator` over the token manager, the main event
dispatcher, the configured token extractors and the firewall's user provider. It
requires the [security](../xtr-security), [clock](../xtr-clock) and
[event dispatcher](../xtr-event-dispatcher) bundles, and the [console](../xtr-console) bundle
when it is installed. It touches no cryptography until a service is asked for — but, needing a
signing key the application must choose, it fails the build when none is configured.

## Errors

Everything the package raises derives from `SecurityError` (from
[xtr-security-core](../xtr-security-core)), so one `except SecurityError` catches it all:

| Error | Base | Raised when |
|---|---|---|
| `JwtFailureError` | `SecurityError` | The base of the signing and verification failures; carries a `reason` and any decoded `payload` |
| `JwtEncodeFailureError` | `JwtFailureError` | A token could not be signed — `invalid_config` or `unsigned_token` |
| `JwtDecodeFailureError` | `JwtFailureError` | A token could not be read — `invalid_token`, `expired_token` or `unverified_token` |
| `ExpiredTokenError` | `AuthenticationError` | A caller presented an expired token — answered with a `401` "Expired JWT Token" |
| `InvalidTokenError` | `AuthenticationError` | A caller presented a malformed, unsigned or tampered token — `401` "Invalid JWT Token" |
| `MissingTokenError` | `AuthenticationError` | A request reached a protected resource with no token — `401` "JWT Token not found" |
| `InvalidPayloadError` | `AuthenticationError` | A verified token carried no user-id claim |

## Layout

```
xtr_security_jwt/
├── encoder/                       the encoder interfaces and the default encoder
├── services/
│   ├── jwt_manager.py             assembles, announces and signs a token
│   ├── jws_provider/              signs and verifies with joserfc
│   ├── key_loader/                reads the signing and verifying key material
│   └── payload_enrichment/        claims added to every token
├── signature/                     the created- and loaded-token value objects
├── security/
│   ├── authenticator/             the JwtAuthenticator and its token
│   └── user/                      the stateless JwtUser and its provider
├── token_extractor/               where a firewall reads a token from
├── event/                         the events dispatched around a token's life
├── exception/                     the errors, one family under one base
├── response/                      the failure response
├── command/                       jwt:generate-keypair, jwt:generate-token, jwt:check-config
├── factory/                       the jwt authenticator factory
├── user_provider/                 the jwt user-provider factory
└── bundle/                        JwtBundle and its configuration
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-security-jwt`; run the commands below from there. The
`python-xtr-security-jwt` repository is a read-only copy, so send issues and pull requests to
the monorepo.

```sh
uv sync --all-packages --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest --cov
```

## License

MIT — see [LICENSE](LICENSE).
