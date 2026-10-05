---
name: xtr-security-jwt
description: How to issue and accept self-issued JSON Web Tokens with xtr-security-jwt. Use when an application must mint an access token for one of its users, write a /token or login endpoint, accept a bearer token on a protected route, configure a signing key or key pair, pass phrase or extra trusted public keys, pick a signature algorithm (RS256, ES256, EdDSA, HS256), publish a JWK set, read a token from a header, cookie or query parameter, add a claim such as jti or a tenant to every token, listen to token created, encoded, decoded, expired, invalid or not-found events, run jwt:generate-keypair, jwt:generate-token or jwt:check-config, or activate JwtBundle and fix the build failure it raises until a signing key and the firewall entry are configured.
---

# xtr-security-jwt

The security family verifies bearer tokens issued elsewhere; this package issues them. An
application signs a token for one of its users, hands it to a client, and accepts it back on a
protected route, with no authorization server in the loop.

Firewalls, access control, voters and user providers belong to the family: load the
`xtr-security` skill for those. This one covers only the JWT half.

## Quick reference

- Inject `JwtTokenManagerInterface` to mint a token: `await tokens.create(user)`.
- `JwtBundle` **fails the build** until `JwtConfig(secret_key=...)` is configured. There is no
  zero-config path. See [Use in an application](#use-in-an-application).
- A firewall accepts tokens by listing `JwtAuthenticatorConfig()` under its `authenticators`;
  a deployment with no user store adds `JwtUserProviderConfig()` as a provider.
- Tokens arrive in the `Authorization: Bearer` header by default; cookies, a query parameter and
  split cookies opt in through `TokenExtractorsConfig`.
- `jwt:generate-keypair` mints a key; `jwt:check-config` proves the configured one works.
- Every failure derives from `SecurityError`.

## Issue a token

```python
from fastapi import FastAPI
from xtr_dependency_injection import Injected
from xtr_security_http import Firewall
from xtr_security_jwt import JwtTokenManagerInterface

app = FastAPI(dependencies=[Firewall()])


@app.post("/token")
async def issue_token(
    identifier: str,
    tokens: Injected[JwtTokenManagerInterface],
) -> dict[str, str]:
    user = await _authenticated_user(identifier)  # your code checks the password
    return {"access_token": await tokens.create(user)}
```

The manager never reads any part of the token from client input: it assembles the claims from
the user you hand it. Authenticate that user **before** calling `create`, and throttle the
endpoint. Reading the user back on a protected route is `CurrentUser()` from the family.

| Call | Does |
| --- | --- |
| `await tokens.create(user)` | Mints a signed token carrying the user's identifier and roles |
| `await tokens.create_from_payload(user, payload)` | The same, starting from claims you supply |
| `await tokens.parse(token)` | Verifies a compact token and returns its claims |
| `await tokens.decode(security_token)` | Claims out of a security token, or `False` when it has none |
| `tokens.get_user_id_claim()` | The claim the identifier is written into |

`create` writes `roles`, the identifier under `user_id_claim`, and the time claims the algorithm
and `token_ttl` imply (`iat`, `exp`).

## Accept a token on a firewall

```python
# app/config/security.py
from xtr_dependency_injection import configure
from xtr_security.bundle import AccessControlConfig, FirewallConfig, SecurityConfig
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

- `JwtAuthenticatorConfig(provider=None, authenticator=None)` takes nothing else: the keys, the
  algorithm and the extractors all come from `JwtConfig`. `provider` overrides the firewall's
  user provider; `authenticator` names a registered service to build instead of the default.
- `JwtUserProviderConfig(user_class=JwtUser)` is the stateless provider, and `JwtUser` carries an
  identifier and the `roles` claim, nothing else. A deployment with a user store names its own
  provider instead and drops this one.

## Configure keys and claims

```python
# app/config/jwt.py
from xtr_dependency_injection import configure, env
from xtr_security_jwt.bundle import EncoderConfig, JwtConfig


@configure
def jwt() -> JwtConfig:
    return JwtConfig(
        secret_key=env("file:JWT_SECRET_KEY_PATH"),
        encoder=EncoderConfig(signature_algorithm="RS256"),
        token_ttl=900,
        user_id_claim="username",
    )
```

The fields that matter most:

| Field | Default | What it is |
| --- | --- | --- |
| `secret_key` | `None` | **Required.** The private key or shared secret, as key text or a file path |
| `public_key` | `None` | The verifying key, or `None` to derive it from the private key |
| `token_ttl` | `3600` | Seconds a minted token lives |
| `clock_skew` | `0` | Seconds of skew tolerated on a verified token's time claims |
| `user_id_claim` | `"username"` | The claim the identifier is written into and read back from |

Every field, the supported algorithms, the pass phrase, extra trusted public keys and the four
token extractors: [references/configuration.md](references/configuration.md).

## Add a claim to every token

Register a `PayloadEnrichmentInterface`; the manager chains every one it is given. Never reach
for the container to stamp a claim, and never edit a signed token.

```python
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_jwt.services.payload_enrichment_interface import PayloadEnrichmentInterface


class TenantEnrichment(PayloadEnrichmentInterface):
    def enrich(self, user: UserInterface, payload: dict[str, object]) -> None:
        payload["tenant"] = "acme"  # edited in place, before signing
```

`RandomJtiEnrichment`, in `xtr_security_jwt.services.payload_enrichment.random_jti_enrichment`,
ships for a unique token id.

## Listen to a token's life

Listen under a constant on `Events`, never by importing the event class. `JWT_CREATED` shapes
the claims before signing, `JWT_DECODED` may reject a verified token, and `JWT_EXPIRED`,
`JWT_INVALID` and `JWT_NOT_FOUND` are the refusals. All nine, with what a listener may do to
each: [references/events-and-errors.md](references/events-and-errors.md).

## Commands

With the `console` extra and a console bundle active:

| Command | Does |
| --- | --- |
| `jwt:generate-keypair [--algorithm RS256] [--kid KID] [--output-dir DIR]` | Mints a key, prints the private PEM and public JWK set, or writes both into `DIR` named by key id |
| `jwt:generate-token IDENTIFIER [--provider NAME]` | Loads the user through a configured provider and prints a token for it |
| `jwt:check-config` | Signs a probe token and reads it back, proving the configured keys work |

## Testing

Boot the kernel and resolve the manager; nothing is mocked, and a throwaway key file keeps the
test self-contained.

```python
import pytest
from xtr_dependency_injection import Kernel
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_jwt import JwtTokenManagerInterface
from xtr_security_jwt.bundle import JwtBundle


@pytest.mark.anyio
async def test_a_token_names_its_user(tmp_path) -> None:
    key = tmp_path / "private.pem"
    key.write_text(PRIVATE_PEM)
    kernel = Kernel(
        "app",
        env="test",
        bundles={JwtBundle: {"all": True}},
        concurrent_scoped_access=True,
        environ={"JWT_SECRET_KEY_PATH": str(key)},
    )

    async with await kernel.build().boot() as booted:
        tokens = await booted.container.get(JwtTokenManagerInterface)
        claims = await tokens.parse(await tokens.create(InMemoryUser("ada", roles=["ROLE_USER"])))

    assert claims["username"] == "ada"
```

- Generate the key in a fixture rather than committing one:
  `RSAKey.generate_key(2048).as_pem(private=True).decode()`, from `joserfc.jwk`.
- Drive a served application through `httpx.ASGITransport` inside its own lifespan, so
  `setup(app, kernel)` builds and boots the kernel for the test.
- Replace a service with `boot_for_test(kernel, overrides={...})` from
  `xtr_dependency_injection.testing`.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists `JwtBundle`,
writes a starting `config/jwt.py`, `JWT_SECRET_KEY_PATH` (commented out) in `.env`, and ignores
`/secrets/*.pem`. That is the steps below a recipe can do; the keypair and firewall steps it prints
for you to make.

1. **Install** — `uv add xtr-security-jwt`; add `[console]` for the commands.
2. **Mint a key** — `jwt:generate-keypair --algorithm RS256 --output-dir secrets/`. The private
   PEM signs, the public JWK set verifies.
3. **Activate** — `JwtBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, from
   `xtr_security_jwt.bundle`. Build the kernel with `concurrent_scoped_access=True` and call
   `setup(app, kernel)` where the application is served, as the security family requires.
4. **Configure, and you must** — this bundle has no zero-config path. Write
   `<app>/config/jwt.py` returning a `JwtConfig(secret_key=...)` and add
   `JwtAuthenticatorConfig()` to a firewall's `authenticators` in `<app>/config/security.py`.
   Without a `secret_key` the build fails with `InvalidConfigurationError`, naming the missing
   setting and the config function to write.
5. **Brings along** — the security, clock and event dispatcher bundles always; the console
   bundle when xtr-console is installed.
6. **Environment** — with `secret_key=env("file:JWT_SECRET_KEY_PATH")`, set
   `JWT_SECRET_KEY_PATH`. It resolves at boot, not at build.
7. **Ignore** — `.gitignore` the private keys when they land in the project: `secrets/*.pem`.
8. **Check** — `debug:bundles` shows `jwt` as `listed` and `active` and `security` as
   `required`; `debug:firewall api` lists the `jwt` authenticator; `jwt:check-config` proves the
   keys sign and verify.
9. **Remove** — drop the `BUNDLES` entry, delete `<app>/config/jwt.py` and the
   `JwtAuthenticatorConfig` from the firewall, then `uv remove xtr-security-jwt`.

## Errors

Import from `xtr_security_jwt.exception`. All derive from `SecurityError`, so one
`except SecurityError` catches every one.

| Error | Raised when |
| --- | --- |
| `JwtFailureError` | The base of the signing and verification failures; carries a `reason` and any decoded `payload` |
| `JwtEncodeFailureError` | `tokens.create` could not sign |
| `JwtDecodeFailureError` | `tokens.parse` could not read, verify or accept the expiry of a token |
| `MissingClaimError` | A token lacks a claim a caller required |
| `ExpiredTokenError`, `InvalidTokenError`, `MissingTokenError`, `InvalidPayloadError` | The firewall's own `401` answers; it raises and handles these itself |

Reasons, messages, and the two errors from outside the family:
[references/events-and-errors.md](references/events-and-errors.md).

## Do not

- Do not build a token from anything a client sent. Authenticate the user, then call `create`.
- Do not commit a private key or write one into `JwtConfig` as literal text; point `secret_key`
  at a file with `env("file:...")`.
- Do not expect `JwtBundle` to boot unconfigured. It is the one bundle here that refuses to.
- Do not verify a token by hand with a JOSE library; `tokens.parse` applies the configured keys,
  algorithm, skew and expiry rules.
- Do not enable the query-parameter extractor unless you accept tokens in logs and referrers.
- Do not reach for the family's generic bearer authenticator for a self-issued token; that one
  is for tokens issued elsewhere.
