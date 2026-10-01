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

Requires Python 3.11+. One sibling comes with it,
[xtr-password-hasher](../xtr-password-hasher), for the password-authenticated user interface.

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
`OidcUser(claims, identifier_claim="sub", roles=("ROLE_USER",))` is a user built from a verified
token's own claims, for a deployment that keeps no user store.

A **`UserProviderInterface`** loads a user by identifier — `load_user_by_identifier(identifier)`,
raising `UserNotFoundError` when none matches — and `supports_class(user_class)` tells which
class it loads. `InMemoryUserProvider` holds a map of identifier to user; `ChainUserProvider`
tries several in order and forwards a `upgrade_password` to whichever can.
`AttributesBasedUserProviderInterface` adds an `attributes` mapping to the load, for a provider
that reads a verified token's claims. `PasswordUpgraderInterface` is the one method a provider
implements to store a freshly rehashed password, and `EquatableInterface.is_equal_to` lets two
users be compared field for field.

A **`UserCheckerInterface`** gates an account around authentication: `check_pre_auth(user)`
before the credentials are verified, `check_post_auth(user, token)` after. `InMemoryUserChecker`
refuses a disabled account with `DisabledError`; `ChainUserChecker` runs several in order.

### Tokens and storage

A **`TokenInterface`** carries the authenticated user (`get_user()`, `get_user_identifier()`),
the roles fixed on it (`get_role_names()`), and a bag of attributes (`get_attribute`,
`set_attribute`, `has_attribute`, `get_attributes`). `AbstractToken` is the base;
`NullToken` is the anonymous caller, with no user and no roles; `UsernamePasswordToken(user,
firewall_name, roles=())` adds the firewall (or unit of work) that authenticated the user,
read back with `get_firewall_name()`.

**`TokenStorage`** holds the current token for one unit of work — `get_token()` /
`set_token(token)` — and `reset()` forgets it so the next one starts clean. The
**`AuthenticationTrustResolver`** reads a token's standing: `is_authenticated(token)` tells
whether anyone is behind it, `is_full_fledged(token)` whether it was fully authenticated this
unit of work.

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
**`AccessDecision`** with every `Vote` cast, the deciding strategy's name, and a `message`
accounting for the outcome. Each `Vote` carries its `voter`, its `result`, the `reasons` the
voter added with `add_reason(...)`, and any `extra_data`.

The built-in voters:

| Voter | Grants on | Reads |
|---|---|---|
| `RoleVoter(prefix="ROLE_")` | a role the token holds | the token's roles |
| `RoleHierarchyVoter(hierarchy, prefix="ROLE_")` | a role the token's roles *reach* | the token's roles, expanded |
| `AuthenticatedVoter(trust_resolver)` | `IS_AUTHENTICATED`, `IS_AUTHENTICATED_FULLY`, `PUBLIC_ACCESS` | the token's standing |
| `ClosureVoter()` | a callable attribute returning `True` | a fresh `IsGrantedContext` |

A **`ClosureVoter`** runs a callable attribute `(IsGrantedContext, subject) -> bool`, so a
one-off rule needs no class; the context it passes can defer to the manager again with
`await context.is_granted(...)`.

### The authorization checker

**`AuthorizationChecker(token_storage, access_decision_manager)`** is the one call the rest of
an application makes: `is_granted(attribute, subject=None)` decides for the token currently in
storage, and `is_granted_for_user(user, attribute, subject=None)` decides for a given user
(`GuestAuthorizationCheckerInterface`) without touching storage. **`IsGrantedContext`** is the
value a closure voter is handed — the `token`, its `user`, and `is_granted(...)` for a nested
question.

### Role hierarchy and wildcards

**`RoleHierarchy(mapping)`** expands a set of roles: `get_reachable_role_names(roles)` returns
the input roles plus every role they reach transitively, with no duplicates and safe against
cycles; `get_parent_role_names(role)` is one level down. A `*` in a key captures a segment of a
matching role and substitutes it into the values, so
`{"ROLE_TENANT_*_ADMIN": ["ROLE_TENANT_*_USER"]}` makes `ROLE_TENANT_42_ADMIN` reach
`ROLE_TENANT_42_USER`.

### Tracing votes and events

**`TraceableVoter(voter, event_dispatcher)`** wraps any voter and announces its answer as a
`VoteEvent` — the voter, the subject, the attributes, the `Access` and the reasons — so a
decision can be read after the fact; `get_decorated_voter()` returns the voter it wraps. The
two event names a dispatcher keys on live in `authentication_events.py`:
`AUTHENTICATION_SUCCESS` (announced once a token is created for an authenticated user, carrying
an `AuthenticationSuccessEvent`) and `VOTE` (announced by a `TraceableVoter`). An
`AuthenticationEvent` carries the `token` it settled on.

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

## Layout

```
xtr_security_core/
├── user/                     UserInterface, InMemoryUser(Provider/Checker), chains, OidcUser
├── authentication/
│   ├── token/                TokenInterface, AbstractToken, NullToken, UsernamePasswordToken
│   │   └── storage/          TokenStorage, the current token per unit of work
│   └── authentication_trust_resolver.py  is a token authenticated, and how fully
├── authentication_events.py  AUTHENTICATION_SUCCESS, VOTE
├── authorization/
│   ├── access_decision_manager.py  gathers voters and decides with a strategy
│   ├── authorization_checker.py    is_granted — the one call the application makes
│   ├── is_granted_context.py       what a closure voter is handed
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
