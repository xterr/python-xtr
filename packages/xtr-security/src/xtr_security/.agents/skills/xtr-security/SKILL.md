---
name: xtr-security
description: Authentication and authorization for an xtr application — firewalls, bearer access tokens, form and OIDC logins, sessions, users and providers, roles, voters, the current user, and password hashing — configured by one SecurityConfig. Use when adding a login or sign-in flow, keeping a session between requests, logging a user out or switching to another one, throttling login attempts, protecting routes or a whole router, reading the current user in an endpoint or a service, checking a role or a permission, writing a voter or an owner-only rule, declaring a user provider, setting a role hierarchy, hashing or verifying a password, choosing a decision strategy, answering 401 or 403, requiring OAuth2 scopes, verifying a third-party OIDC issuer's tokens, minting the application's own OIDC token, or activating SecurityBundle in an application on xtr-dependency-injection.
---

# xtr-security

Two questions, kept apart. *Who is calling?* settles on a **token** — a user and the roles fixed
on them for this request, settled by a **firewall** over a slice of the request space. *May
they?* asks a set of **voters** and folds the answers into one decision, through access control,
`IsGranted` or the `Security` facade.

This is the bundle of the family: depend on it and the core (users, tokens, roles, voters), the
HTTP edge (firewalls, authenticators, the route surface) and the password hasher come with it.
Write one `SecurityConfig`; the container owns the rest.

## Quick reference

| Want | Write |
| --- | --- |
| Protect the routes | a firewall in `SecurityConfig.firewalls`; the bundle runs them |
| Require a role on a route | `@IsGranted("ROLE_ADMIN")` under the route decorator |
| Require it over a subject | `dependencies=[IsGranted("BOOK_EDIT", subject=load_book)]` |
| The current user in an endpoint | `user: Annotated[UserInterface, CurrentUser()]` |
| The authenticated token in an endpoint | `token: Annotated[TokenInterface, CurrentToken()]` |
| Require a form's CSRF token | `dependencies=[IsCsrfTokenValid("delete_book", methods=["POST"])]` |
| The current user, or a decision, in a service | inject `Security` |
| Refuse in a service | `await security.deny_access_unless_granted("EDIT", book)` |
| A rule of your own | a class extending `Voter`, registered `@as_service` |
| Hash a password | inject `UserPasswordHasherInterface` |
| Require scopes | an `AccessControlConfig` with an `oauth2_scope(...)` attribute |
| Keep a session (form login, logout, remember me) | `stateless=False` plus a `SessionStorageInterface` service |
| Sign in with an OIDC provider | `OidcLoginConfig` behind the `oidc` extra |
| Mint this application's own OIDC token | a `token_generator` block, then `security:oidc:generate-token` |

Import from these surfaces, nothing deeper: `xtr_security` (`Security`), `xtr_security.bundle`
(every `*Config` and `SecurityBundle`), `xtr_security_core` (users, tokens, voters, errors),
`xtr_security_http` (`IsGranted`, `CurrentUser`, `CurrentToken`, `IsCsrfTokenValid`, badges) and
`xtr_password_hasher`.

Self-issued JSON Web Tokens are an add-on package, `xtr-security-jwt`, with a skill of its own
(`xtr-security-jwt`); it plugs its authenticator into this bundle.

## Configure the firewalls

One `@configure` function in `<app>/config/packages/security.py`. Every field has a default, so start
small and add.

```python
from xtr_dependency_injection import configure
from xtr_security.bundle import (
    AccessControlConfig,
    AccessTokenConfig,
    AutoHasherConfig,
    FirewallConfig,
    InMemoryUserProviderConfig,
    SecurityConfig,
    ServiceTokenHandlerConfig,
)
from xtr_security_core import InMemoryUser

from app.security_handler import MyTokenHandler  # your AccessTokenHandlerInterface service

_ADA = {"password": _ADA_HASH, "roles": ("ROLE_USER",)}


@configure
def security() -> SecurityConfig:
    return SecurityConfig(
        providers={  # one entry per name a firewall's `provider` refers to
            "users": InMemoryUserProviderConfig(users={"ada@example.com": _ADA}),
        },
        password_hashers={InMemoryUser: AutoHasherConfig()},
        role_hierarchy={"ROLE_ADMIN": ("ROLE_USER",)},
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                provider="users",
                authenticators=(
                    AccessTokenConfig(
                        token_handler=ServiceTokenHandlerConfig(service=MyTokenHandler),
                        realm="api",
                    ),
                ),
            ),
        },
        access_control=(
            AccessControlConfig(path=r"^/api/admin", attribute="ROLE_ADMIN"),
            AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),
        ),
    )
```

- Firewalls are matched in order; the first whose `pattern`, `host`, `methods` or
  `request_matcher` — a callable `(ServerRequestInterface) -> bool` — claims the request wins.
  The matchers come from `xtr-http-foundation` and read the request as a message. A firewall with
  none of them claims everything, so it goes last.
- `access_control` rules are tried in order too, so the narrow `^/api/admin` rule comes before
  the broad `^/api`. One attribute per rule: a role, `"IS_AUTHENTICATED"`, `"PUBLIC_ACCESS"`, or
  an `OAUTH2_SCOPE(...)` string the `oauth2_scope(...)` helper builds.
- `role_hierarchy` expands the token's roles, so `ROLE_ADMIN` need not list `ROLE_USER`.
- Every string in a bundle config is parameter-resolved: write a literal `%` as `%%`, and read
  secrets with `env("...")`.

Field tables for the whole surface — every authenticator and token handler, the firewall
blocks (logout, switch user, throttling), the OIDC flow, secrets, the channel and the
authenticator seam:
[references/firewalls-and-authenticators.md](references/firewalls-and-authenticators.md).

## Go stateful: sessions, logins and logout

A stateful firewall (`stateless=False`) restores the token its session carries on every
request. The session storage is the application's to register — the bundle never builds one,
and a stateful firewall with none registered fails the build naming the service:

```python
from xtr_dependency_injection import as_service
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface


@as_service
def session_storage() -> SessionStorageInterface:
    return MemorySessionStorage()  # one process; a cache-pool storage for a shared backend
```

```python
"main": FirewallConfig(
    pattern=r"^/",
    stateless=False,
    provider="users",
    session_strategy="migrate",  # the default: rotate the session ID on a login
    logout=LogoutConfig(path="/logout", target_path="/", enable_csrf=True),
    authenticators=(FormLoginConfig(login_path="/login", enable_csrf=True),),
)
```

- A successful login hands the session to `session_strategy`: `migrate` rotates its ID keeping
  its attributes, `invalidate` empties it, `none` leaves it alone.
- On the response side a `SaveSessionListener` writes the session through the storage and
  stages the cookie carrying its ID — a storage that fails fails the request loudly rather
  than losing the session quietly.
- The cross-site request forgery machinery is opt-in, wired by one of four triggers: a form
  login with `enable_csrf`, a logout with `enable_csrf` or `clear_csrf_tokens`, a
  `switch_user` block with `enable_csrf`, or the firewall's `csrf_route_markers`. The tokens
  travel in the session, so a stateless firewall asking for any of them fails the build.
- A switch (`switch_user=SwitchUserConfig()`) lets a caller holding
  `ROLE_ALLOWED_TO_SWITCH` become another user by carrying `_switch_user`, and step back out
  with `_exit`; the bundle hands the step the firewall's dispatcher, so its `SwitchUserEvent`
  reaches the firewall's listeners.

## Sign in with an OIDC provider

Behind the `oidc` extra (`uv add "xtr-security-http[oidc]"`), an `OidcLoginConfig` builds the
authorization-code login, on a stateful firewall with a user provider:

```python
"main": FirewallConfig(
    pattern=r"^/",
    stateless=False,
    provider="users",
    authenticators=(
        OidcLoginConfig(
            issuer="https://issuer.example",
            client_id="shop",
            client_secret=env("OIDC_CLIENT_SECRET"),
            signature_verifier_algorithms=("RS256",),
        ),
    ),
)
```

The provider is discovered from `issuer`, PKCE is on (`S256`) by default, and the user is read
from the `userinfo` endpoint or the `id_token` claims by `user_data_source`. The callback
answers on `check_path` (`/oidc/callback`). On a stateless firewall the login fails at use
with `MissingSessionError`, not at build — its pending attempts live in the session. A
`token_generator` block makes this application's own tokens mintable through
`security:oidc:generate-token`; `backchannel_logout` and `end_session` wire the
provider-pushed logout, whose route is the application's to map. The fields and the back
channel: [references/firewalls-and-authenticators.md](references/firewalls-and-authenticators.md).

## Read a secret from the environment

Three configurations sign or derive with a `secret`: the remember-me cookie, the login link
and the login throttling. Each is a plain configuration field, so the application's own
`configure` reads it the way every other setting is read — `RememberMeConfig(secret=
env("REMEMBER_ME_SECRET"))`. The bundle never mints one: it builds and boots without any of
them, and the service that needs one fails the first time it is asked for, naming the
setting. An empty value reads as no secret at all.

## Protect a route, and read the user

```python
from typing import Annotated

from fastapi import APIRouter, FastAPI
from xtr_security_core import UserInterface
from xtr_security_http import CurrentUser, IsGranted

app = FastAPI()
router = APIRouter(prefix="/api")


@router.get("/me")
async def me(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, object]:
    return {"identifier": user.get_user_identifier(), "roles": list(user.get_roles())}


@router.delete("/books/{isbn}")
@IsGranted("ROLE_ADMIN")
async def delete_book(isbn: str) -> None: ...
```

- The firewalls the configuration matches run as the firewall — a subscriber the bundle
  registers over the kernel lifecycle's events, before routing — so the routes carry no
  firewall dependency of their own and the generated schema shows only what a route declares
  natively.
- `CurrentUser()` raises on an anonymous request, answered `401`. `optional=True` yields `None`
  instead, for a parameter typed `UserInterface | None`; `CurrentUser(MyUser)` requires a class.
- `IsGranted` takes a `subject` in `dependencies=[...]`: a path-parameter name, or a callable
  shared with the endpoint through `Depends`. A denial is `403` for a fully authenticated caller
  and `401` for an anonymous one, or `status_code=` answered directly.
- `IsGranted` never consumes the scopes a route declared natively with `Security(..., scopes=...)`
  unless the route opts in with `consume_security_scopes=True`; opted in, each accumulated scope
  is decided through the voters too. `IsCsrfTokenValid(token_id)` refuses a request whose presented
  value the token manager does not vouch for, with a `403`.

## Decide in a service

```python
from xtr_security import Security


class PublishBook:
    def __init__(self, security: Security) -> None:
        self._security = security

    async def publish(self, book: Book) -> None:
        await self._security.deny_access_unless_granted("BOOK_PUBLISH", book)
```

`Security` answers `get_token()`, `get_user()`, `is_granted(attribute, subject=None)`,
`is_granted_for_user(user, attribute, subject=None)` — `None` for a guest — and
`deny_access_unless_granted(...)`, and is
scoped to the request — a singleton cannot depend on it, so take it as a method argument or make
the service scoped too.

## Write a voter

A class implementing `VoterInterface` is gathered into the decision manager by the bundle's
`security.voter` tag. Extend `Voter`, register it as a service, and that is the whole wiring.

```python
from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_security_core import TokenInterface, Vote, Voter


@as_service
class OrderViewVoter(Voter):
    @override
    def supports(self, attribute: object, subject: object) -> bool:
        return attribute == "ORDER_VIEW" and isinstance(subject, Order)

    @override
    async def vote_on_attribute(
        self, attribute: object, subject: object, token: TokenInterface, vote: Vote | None
    ) -> bool:
        owner = subject.email == token.get_user_identifier()
        if vote is not None and not owner:
            vote.add_reason("the order belongs to another customer")
        return owner
```

Keep `supports` narrow: a voter that speaks about everything drowns out the others under the
affirmative strategy. A one-off rule needs no class — an `IsGranted` attribute may be a callable
`(IsGrantedContext, subject) -> bool`, run by the built-in closure voter.

Strategies, the built-in voters, scopes and the hierarchy's wildcards:
[references/authorization.md](references/authorization.md).

## Hash and verify a password

Inject `UserPasswordHasherInterface`; it reads the stored hash off the user itself.

```python
# in an async service, hashing is CPU-bound: never run it on the event loop
user.password = await anyio.to_thread.run_sync(hasher.hash_password, user, plain_password)
ok = await anyio.to_thread.run_sync(hasher.is_password_valid, user, attempt)
stale = hasher.needs_rehash(user)  # re-store right after a successful check
```

`password_hashers` maps each user class to its hasher; `AutoHasherConfig()` is argon2id with
bcrypt and PBKDF2 verifying behind it, so a hash from an older algorithm still verifies and
`needs_rehash` says when to replace it. Costs, migrations and the command:
[references/password-hashing.md](references/password-hashing.md).

## Testing

Voters, hashers and the decision are plain objects — test them with no kernel.

```python
import pytest
from xtr_security_core import Access, InMemoryUser, UsernamePasswordToken

pytestmark = pytest.mark.anyio


async def test_a_voter_refuses_another_customers_order() -> None:
    ada = InMemoryUser("ada@example.com", roles=["ROLE_USER"])
    token = UsernamePasswordToken(ada, "api", roles=ada.get_roles())
    order = Order("lin@example.com")

    assert await OrderViewVoter().vote(token, order, ["ORDER_VIEW"]) is Access.DENIED
```

A whole decision needs no kernel either: an `AccessDecisionManager(voters=[...],
strategy=AffirmativeStrategy())` over a `TokenStorage`, asked through
`AuthorizationChecker(storage, manager)`. The wired services — the token storage, the authorization checker, `Security`, the firewall map —
are **scoped**, so reach them inside a unit of work:

```python
from xtr_dependency_injection import unit_of_work
from xtr_dependency_injection.testing import boot_for_test

async with await boot_for_test(kernel) as booted, unit_of_work(booted.container) as unit:
    security = await unit.get(Security)
```

End to end, sign a request the way a client does — call your own token route, send the credential
back — rather than writing a token into storage by hand.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`SecurityBundle`, which brings the event dispatcher and http-kernel bundles with it, and writes
`<app>/config/packages/security.py` with the bundle's own defaults. That is the steps below a
recipe can do; the `concurrent_scoped_access`, `setup(app, kernel)` and firewall steps it prints
for you to make.

1. **Install** — `uv add xtr-security`; xtr-console, installed beside it, adds `debug:firewall`
   and `security:hash-password` — and `security:oidc:generate-token` when a firewall's OIDC
   login mints. `"xtr-security-http[oidc]"` adds verifying third-party OIDC issuers' tokens
   and the OIDC login.
2. **Activate** — `SecurityBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`, imported
   from `xtr_security.bundle`. Call `setup(app, kernel)` where the application is built, and
   build the kernel with `concurrent_scoped_access=True` so concurrent requests keep their own
   token storage.
3. **Brings along** — the event-dispatcher and http-kernel bundles always; the clock bundle,
   installed with the security core, whose clock the trust resolver reads; the logging and
   console bundles whenever those packages are installed.
4. **Configure** — the recipe writes `<app>/config/packages/security.py` holding the defaults: no
   firewall yet, and the affirmative strategy. Changing what its `@configure` function returns,
   a `SecurityConfig`, changes it.
5. **Environment** — nothing of its own; read your secrets with `env(...)` in the configuration.
6. **Ignore** — nothing.
7. **Check** — `debug:bundles` shows `security` as `listed` and `active`, `event_dispatcher`,
   `http_kernel` and `clock` as `required`; `debug:firewall [name]` lists or describes the
   firewalls.
8. **Remove** — drop the `BUNDLES` entry; `uv run xtr-recipes recipes:remove xtr-security`
   deletes `<app>/config/packages/security.py`, unless you edited it, in which case it is moved
   aside to `security.py.removed`. Then `uv remove xtr-security`.

## Errors

Everything the family raises derives from `SecurityError` (`xtr_security_core.exception`).

| Error | Raised when |
| --- | --- |
| `InvalidConfigurationError` | A configuration the bundle cannot turn into services — an unknown provider, a secured firewall with no authenticator, an authenticator with no factory, a stateful firewall with no `SessionStorageInterface` registered. Also a `ValueError` |
| `AuthenticationError` | Authentication failed, answered `401`. The base of `BadCredentialsError` (rejected), `AuthenticationCredentialsNotFoundError` (none presented — what `CurrentUser()` raises when anonymous), `InvalidAccessTokenError` (a bearer token present but untrusted), `InvalidCsrfTokenError` (a form's forgery token present but untrusted), `UserNotFoundError`, and the account-state errors `DisabledError`, `LockedError`, `AccountExpiredError` |
| `AccessDeniedError` | Authorization refused; carries `attributes`, `subject` and `access_decision` |
| `UnknownFirewallError` | A firewall was asked for by a name none is registered under |
| `InvalidPasswordError` | A password encodes to more than `MAX_PASSWORD_LENGTH` (4096) UTF-8 bytes |
| `MissingSessionError` | A login needing a session — the OIDC login parking a pending attempt — ran on a stateless firewall. Raised at use, not at build |

Catch them where you answer them; the firewall's exception listener already turns an uncaught one
into the right status and challenge.

## Do not

- Do not read the `Authorization` header, or parse a credential, in an endpoint. That is the
  firewall's job: write a token handler or an authenticator instead.
- Do not build `TokenStorage`, `AuthorizationChecker`, `AccessDecisionManager` or
  `PasswordHasherFactory` by hand — the bundle registers each; inject it.
- Do not call a hasher on the event loop; wrap it in `anyio.to_thread.run_sync`.
- Do not store a plaintext password, and do not use `PlaintextHasherConfig()` outside a test.
- Do not depend on a scoped security service from a singleton; take it as an argument.
- Do not write a voter whose `supports` is broadly `True`: under the affirmative strategy one
  careless grant decides everything.
- Do not set `security=False` on a firewall to make a `401` go away: that opens every request it
  claims. Give the open routes a `PUBLIC_ACCESS` access-control rule instead.
- Do not trust a claim from client input when minting a user; read the roles from your own store.
- Do not generate a secret for the remember-me, login-link or throttling configurations: read
  the environment in your own `configure`, and let the missing one fail at use naming the
  setting.
- Do not reach for `MemorySessionStorage` where several servers answer: the storage a stateful
  firewall reattaches must be shared, or one server's login is the next server's stranger.
- Do not expect the bundle to serve the back-channel logout route: it registers the
  `OidcBackChannelLogoutHandler`; mapping the path the provider pushes to is the
  application's.
- Do not read a submission's fields off the parsed body in a firewall listener: the chain runs
  before the body is materialised, so they ride the query string there. A route reads the body
  as ever.
