<div align="center">

# xtr-security-core

**The security core: users, tokens, roles, voters and the authorization decision.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Two questions sit under every protected feature: *who is this?* and *may they do this?* The
first settles on a **token** — a user and the roles fixed on them for this unit of work. The
second asks a set of **voters** and folds their answers into one yes or no with a **strategy**.
Keeping the two apart, and keeping the decision a small pluggable thing, is what lets a web edge,
a console command and a background job all reach the same answer the same way.

This package is that core, with no web framework and no container in sight:

- 🪪 **Users and providers** — a `UserInterface` is an identifier and a set of roles; a provider
  loads one by identifier, from memory or from anywhere an application writes.
- 🎫 **Tokens and storage** — a token carries the authenticated user and their roles; a
  per-unit-of-work storage holds the current one.
- 🗳️ **Voters, strategies and one decision** — each voter grants, denies or abstains on an
  attribute; a strategy turns the votes into a decision, and the `AuthorizationChecker` is the
  one call the rest of the application makes.
- 🪜 **A role hierarchy** — one role reaches others, wildcards included, so `ROLE_ADMIN` need
  not list every role it implies.

The HTTP edge — firewalls, authenticators, bearer tokens — is a separate package,
[xtr-security-http](../xtr-security-http); the OAuth2 scope voter lives there, since scopes are a
request concern.

## Install

```sh
uv add xtr-security-core
```

Requires Python 3.11+. Two siblings come with it:
[xtr-password-hasher](../xtr-password-hasher), for the password-authenticated user interface, and
[xtr-clock](../xtr-clock), the clock the trust resolver measures recent authentication with.

## Quick start

Everything below runs without a container: build a user provider, a decision manager over a few
voters, and ask the checker. The roles on the token are expanded through the hierarchy, and a
voter you write joins the others by implementing `Voter`:

```python
from __future__ import annotations

import asyncio

from xtr_security_core import (
    AccessDecisionManager,
    AffirmativeStrategy,
    AuthenticatedVoter,
    AuthenticationTrustResolver,
    AuthorizationChecker,
    ClosureVoter,
    InMemoryUser,
    InMemoryUserProvider,
    IsGrantedContext,
    RoleHierarchy,
    RoleHierarchyVoter,
    TokenStorage,
    UsernamePasswordToken,
    Vote,
    Voter,
)
from xtr_security_core.authentication.token.token_interface import TokenInterface


class Document:
    def __init__(self, owner: str) -> None:
        self.owner = owner


class OwnsDocumentVoter(Voter):
    def supports(self, attribute: object, subject: object) -> bool:
        return attribute == "EDIT" and isinstance(subject, Document)

    async def vote_on_attribute(
        self,
        attribute: object,
        subject: object,
        token: TokenInterface,
        vote: Vote | None,
    ) -> bool:
        assert isinstance(subject, Document)
        return subject.owner == token.get_user_identifier()


async def main() -> None:
    provider = InMemoryUserProvider(
        {
            "ada": InMemoryUser("ada", roles=["ROLE_ADMIN"]),
            "lin": InMemoryUser("lin", roles=["ROLE_USER"]),
        }
    )
    ada = await provider.load_user_by_identifier("ada")

    hierarchy = RoleHierarchy({"ROLE_ADMIN": ["ROLE_USER"]})
    manager = AccessDecisionManager(
        voters=[
            RoleHierarchyVoter(hierarchy),
            AuthenticatedVoter(AuthenticationTrustResolver()),
            OwnsDocumentVoter(),
            ClosureVoter(),
        ],
        strategy=AffirmativeStrategy(),
    )

    storage = TokenStorage()
    storage.set_token(UsernamePasswordToken(ada, "main", roles=ada.get_roles()))
    checker = AuthorizationChecker(storage, manager)

    print("ROLE_USER (via hierarchy):", await checker.is_granted("ROLE_USER"))
    print("IS_AUTHENTICATED:", await checker.is_granted("IS_AUTHENTICATED"))
    print("EDIT own doc:", await checker.is_granted("EDIT", Document(owner="ada")))
    print("EDIT other's doc:", await checker.is_granted("EDIT", Document(owner="lin")))

    async def can_publish(context: IsGrantedContext, subject: object) -> bool:
        return await context.is_granted("ROLE_ADMIN")

    print("closure can_publish:", await checker.is_granted(can_publish))


asyncio.run(main())
```

```console
ROLE_USER (via hierarchy): True
IS_AUTHENTICATED: True
EDIT own doc: True
EDIT other's doc: False
closure can_publish: True
```

## Concepts

### Users, providers and checkers

A **`UserInterface`** is the smallest useful account: `get_user_identifier()` names it, and
`get_roles()` returns the roles it carries. `InMemoryUser(identifier, password=None, roles=(),
enabled=True)` is one for tests and small deployments; it also answers `get_password()` (it is a
[password-authenticated user](../xtr-password-hasher)), `is_enabled()` and `is_equal_to(other)`.
`OidcUser(user_identifier=None, roles=("ROLE_USER",), sub=..., name=..., email=..., ...)` carries
the OpenID Connect standard claims, each read back with its getter (`get_sub()`, `get_email()`,
…), and keeps every other keyword as an additional claim (`get_additional_claims()`); it is
identified by `user_identifier` when given, by the required `sub` otherwise.
`OidcUser.from_claims(claims)` builds one from a provider's claims — every claim is mapped, so
only pass claims you trust. `OAuth2User(roles=("ROLE_USER",), scope=..., client_id=..., sub=...,
username=..., ...)` carries a token introspection response, identified by its `sub`, else its
`username`.

A **`UserProviderInterface`** loads a user by identifier — `load_user_by_identifier(identifier)`,
raising `UserNotFoundError` when none matches — reloads one held from an earlier unit of work —
`refresh_user(user)`, raising `UnsupportedUserError` for a user of a class it does not load —
and `supports_class(user_class)` tells which class it loads. `InMemoryUserProvider` holds a map
of identifier to user; `ChainUserProvider` tries several in order, refreshes with the first that
supports the user, and forwards a `upgrade_password` to whichever can. `OidcUserProvider` builds
an `OidcUser` from the claims authentication collected — which can neither grant roles nor change
the identifier — and returns it as-is on refresh. `MissingUserProvider(firewall)` stands for the
provider of a firewall that needs one and has none: building it raises, naming the firewall.
`AttributesBasedUserProviderInterface` adds an `attributes` mapping to the load, for a provider
that reads a verified token's claims. `PasswordUpgraderInterface` is the one method a provider
implements to store a freshly rehashed password, and `EquatableInterface.is_equal_to` lets two
users be compared field for field.

A **`UserCheckerInterface`** gates an account around authentication: `check_pre_auth(user)`
before the credentials are verified, `check_post_auth(user, token)` after. `InMemoryUserChecker`
refuses a disabled account with `DisabledError`; `ChainUserChecker` runs several in order.

### Tokens and storage

A **`TokenInterface`** carries the authenticated user (`get_user()`, `get_user_identifier()`),
set with `set_user(user)`, the roles fixed on it (`get_role_names()`), a bag of attributes
(`get_attribute`, `set_attribute`, `set_attributes`, `has_attribute`, `get_attributes`), and the
authentication proofs — `get_authentication_proofs()` / `set_authentication_proofs(proofs)`, each
**`AuthenticationMethod`** value (`PASSWORD`, `ONE_TIME_PASSWORD`, … as RFC 8176 names them)
mapped to the Unix timestamp of its last proof. `AbstractToken(roles=())` is the base: the user is
set afterwards, and setting it leaves the roles untouched. `NullToken` is the anonymous caller —
no user, no roles, no attributes — and refuses a user, an attribute or a proof with
`BadMethodCallError`. `UsernamePasswordToken(user, firewall_name, roles=())` adds the firewall
(or unit of work) that authenticated the user, read back with `get_firewall_name()`.
`OfflineTokenInterface` marks the token `is_granted_for_user` decides with; it is read from a
token's class hierarchy, not structurally.

**`TokenStorage`** holds the current token for one unit of work — `get_token()` /
`set_token(token)` — and `reset()` forgets it so the next one starts clean.
`set_initializer(callable)` defers producing the token: the callable runs once, the first time
the token is read or just before one is stored.

The **`AuthenticationTrustResolver(recent_lifetime=7200, very_recent_lifetime=300, clock=None)`**
reads a token's standing: `is_authenticated(token)` tells whether a user is behind it,
`is_remember_me(token)` whether it was remembered rather than proven (never, here: no remembered
token exists), `is_full_fledged(token)` whether it is authenticated and not remembered, and
`is_authenticated_recently(token)` / `is_authenticated_very_recently(token)` whether its last
authentication proof falls within the two windows, read from the clock — the system clock when
none is given.

### Voters, strategies and the decision

A **`VoterInterface`** answers `vote(token, subject, attributes) -> Access`, where
`Access` is `GRANTED`, `DENIED` or `ABSTAIN`. Write one by subclassing **`Voter`** and
answering `supports(attribute, subject)` and `vote_on_attribute(attribute, subject, token,
vote)`; a `CacheableVoterInterface` additionally declares `supports_attribute` /
`supports_type` so the manager can skip a voter that will never speak.

The **`AccessDecisionManager(voters, strategy)`** gathers the votes and folds them with a
**strategy**:

| Strategy | Grants when |
|---|---|
| `AffirmativeStrategy` | any voter grants (the default) |
| `ConsensusStrategy` | grants outnumber denials |
| `UnanimousStrategy` | no voter denies |
| `PriorityStrategy` | the first voter that does not abstain grants |

Each takes `allow_if_all_abstain` (and `ConsensusStrategy` a tie-breaker). `decide(token,
attributes, subject=None, access_decision=None)` reports one `bool`, filling an optional
**`AccessDecision`** with every `Vote` cast, the deciding strategy's name — its `str()`:
`affirmative`, `consensus`, `unanimous`, `priority` — and a `message` accounting for the
outcome. Each `Vote` carries its `voter`, its `result`, the `reasons` the voter added with
`add_reason(...)`, any `extra_data`, and the `re_authentication_attribute` a voter set with
`request_re_authentication(attribute)` when a fresh authentication could grant what it denied.

The built-in voters:

| Voter | Grants on | Reads |
|---|---|---|
| `RoleVoter(prefix="ROLE_")` | a role the token holds | the token's roles |
| `RoleHierarchyVoter(hierarchy, prefix="ROLE_")` | a role the token's roles *reach* | the token's roles, expanded |
| `AuthenticatedVoter(trust_resolver)` | `IS_AUTHENTICATED_VERY_RECENTLY`, `IS_AUTHENTICATED_RECENTLY`, `IS_AUTHENTICATED_FULLY`, `IS_AUTHENTICATED_REMEMBERED`, `IS_AUTHENTICATED`, `IS_REMEMBERED`, `IS_IMPERSONATOR` (never, as yet), and `PUBLIC_ACCESS` asked alone | the token's standing |
| `ClosureVoter()` | a callable attribute returning `True` | a fresh `IsGrantedContext` |

A denied recency attribute requests a re-authentication on its vote, and only the reason of the
strictest attribute that failed is reported. Asking an authentication attribute about an offline
token that carries a user raises `InvalidArgumentError`: how that user authenticated is unknown.

A **`ClosureVoter`** runs a callable attribute `(IsGrantedContext, subject) -> bool`, so a
one-off rule needs no class. Each question the closure asks through its context is decided for
the same token in a decision of its own; the voter reports the reasons those checks gave
(`Closure <name> returned true.` / `… returned false.`), and forwards a re-authentication one of
them requested.

### The authorization checker

**`AuthorizationChecker(token_storage, access_decision_manager)`** is the one call the rest of
an application makes: `is_granted(attribute, subject=None)` decides for the token currently in
storage — the anonymous `NullToken` when none is set, or when the one set carries no user — and
`is_granted_for_user(user, attribute, subject=None)` decides for a given user, or for a guest
with `None` (`UserAuthorizationCheckerInterface`, `GuestAuthorizationCheckerInterface`), against
an offline token built from the user's roles; a voter asking this checker while that decision
runs is answered for the same offline token. **`IsGrantedContext`** is the value a closure voter
is handed — the `token`, its `user`, `is_granted(...)` for a nested question, and the
`is_authenticated()`, `is_authenticated_fully()`, `is_authenticated_recently()`,
`is_authenticated_very_recently()` and `is_impersonator()` shortcuts.

**`TraceableAccessDecisionManager(manager)`** decorates a decision manager to log every decision:
its attributes, subject, result, and the votes fed to it through `add_voter_vote(...)`; read them
back with `get_decision_log()`, `get_voters()` and `get_strategy()`, and `reset()` between units
of work.

### Role hierarchy and wildcards

**`RoleHierarchy(mapping)`** expands a set of roles: `get_reachable_role_names(roles)` returns
the input roles plus every role they reach transitively, with no duplicates and safe against
cycles. A `*` in a key captures a segment of a
matching role and substitutes it into the values, so
`{"ROLE_TENANT_*_ADMIN": ["ROLE_TENANT_*_USER"]}` makes `ROLE_TENANT_42_ADMIN` reach
`ROLE_TENANT_42_USER`. `get_parent_role_names(roles)` asks the inverse question: the input roles
plus every declared role that reaches one of them — a wildcard key is a pattern, never a parent.

### Tracing votes and events

**`TraceableVoter(voter, event_dispatcher)`** wraps any voter and announces its answer as a
`VoteEvent` — the voter, the subject, the attributes, the `Access` and the reasons — so a
decision can be read after the fact; `get_decorated_voter()` returns the voter it wraps. A
dispatcher keys on an event's qualified class name, so a listener names the class it listens
to: `AuthenticationSuccessEvent` (once a token is created for an authenticated user) and
`VoteEvent` (announced by a `TraceableVoter`). An `AuthenticationEvent` carries the `token` it
settled on. `AuthenticationEvents.AUTHENTICATION_SUCCESS` names the success event for a listener
registered by name.

## Errors

Everything this library raises derives from `SecurityError`, and carries what went wrong as
typed attributes rather than only a message.

| Error | Base (besides `SecurityError`) | Raised when |
|---|---|---|
| `AccessDeniedError` | — | authorization refused a known caller; carries `attributes`, `subject`, `access_decision` |
| `AuthenticationError` | — | authentication failed; carries a `message_key` and `message_data` |
| `AccountStatusError` | `AuthenticationError` | the account's own state refuses it; carries the `user` |
| `AccountExpiredError` | `AccountStatusError` | the account has expired |
| `CredentialsExpiredError` | `AccountStatusError` | the account's credentials have expired |
| `DisabledError` | `AccountStatusError` | the account is disabled |
| `LockedError` | `AccountStatusError` | the account is locked |
| `CustomUserMessageAccountStatusError` | `AccountStatusError` | an account-status failure whose public text is chosen at the raise site |
| `AuthenticationCredentialsNotFoundError` | `AuthenticationError` | no credentials were found in the request |
| `AuthenticationServiceError` | `AuthenticationError` | a service authentication relies on failed |
| `BadCredentialsError` | `AuthenticationError` | the credentials presented were rejected |
| `CustomUserMessageAuthenticationError` | `AuthenticationError` | an authentication failure whose public text is chosen at the raise site |
| `InsufficientAuthenticationError` | `AuthenticationError` | authenticated, but not strongly enough |
| `UserNotFoundError` | `AuthenticationError`, `LookupError` | no user matched the identifier |
| `InvalidArgumentError` | `ValueError` | a declaration, configuration or call was malformed |
| `UnsupportedUserError` | `TypeError` | a user of the wrong class reached a provider, checker or resolver |
| `BadMethodCallError` | — | a method was called on an object that refuses it by design — setting anything on a `NullToken` |

## Layout

```
xtr_security_core/
├── authentication_events.py  AuthenticationEvents, the authentication event names
├── user/                     UserInterface, InMemoryUser(Provider/Checker), chains, OidcUser(Provider), OAuth2User
├── authentication/
│   ├── authentication_method.py  AuthenticationMethod, the methods a proof names
│   ├── token/                TokenInterface, AbstractToken, NullToken, OfflineTokenInterface, UsernamePasswordToken
│   │   └── storage/          TokenStorage, the current token per unit of work
│   └── authentication_trust_resolver.py  is a token authenticated, and how fully
├── authorization/
│   ├── access_decision_manager.py  gathers voters and decides with a strategy
│   ├── authorization_checker.py    is_granted — the one call the application makes
│   ├── is_granted_context.py       what a closure voter is handed
│   ├── traceable_access_decision_manager.py  logs every decision and its votes
│   ├── strategy/             affirmative, consensus, unanimous, priority
│   └── voter/                VoterInterface, Voter, Access, Vote, the built-in voters
├── role/                     RoleHierarchy, incl. wildcards
├── event/                    AuthenticationSuccessEvent, VoteEvent
└── exception/                SecurityError, the root of everything this library raises
```

## In an application

This package works on its own and ships no bundle. The
[`xtr-security`](../xtr-security#use-in-an-application) bundle wires it — the token storage, the
role hierarchy, the voters and decision manager, the authorization checker — into an application
on [xtr-dependency-injection](../xtr-dependency-injection); see that package's
[Use in an application](../xtr-security#use-in-an-application). A class implementing
`VoterInterface` is gathered into the decision manager by the bundle's `security.voter` tag.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-security-core`; run the commands below from there. The `python-xtr-security-core`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
