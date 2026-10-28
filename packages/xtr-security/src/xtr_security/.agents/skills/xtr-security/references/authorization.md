# Authorization: voters, strategies, roles and scopes

An attribute is asked over an optional subject. Every voter grants, denies or abstains; a strategy
folds the answers into one decision. `Security` (or `AuthorizationChecker`) is the one call the
rest of the application makes.

## The decision, with no container

```python
from xtr_security_core import (
    AccessDecisionManager,
    AffirmativeStrategy,
    AuthenticatedVoter,
    AuthenticationTrustResolver,
    AuthorizationChecker,
    InMemoryUser,
    RoleHierarchy,
    RoleHierarchyVoter,
    TokenStorage,
    UsernamePasswordToken,
)

hierarchy = RoleHierarchy({"ROLE_ADMIN": ("ROLE_USER",)})
manager = AccessDecisionManager(
    voters=[
        RoleHierarchyVoter(hierarchy),
        AuthenticatedVoter(AuthenticationTrustResolver()),
        OrderViewVoter(),
    ],
    strategy=AffirmativeStrategy(),
)

ada = InMemoryUser("ada@example.com", roles=["ROLE_USER"])
storage = TokenStorage()
storage.set_token(UsernamePasswordToken(ada, "api", roles=ada.get_roles()))
checker = AuthorizationChecker(storage, manager)

await checker.is_granted("ROLE_USER")  # True
await checker.is_granted("ORDER_VIEW", Order("lin@example.com"))  # False
await checker.is_granted("IS_AUTHENTICATED")  # True
```

In an application the bundle builds exactly this from the configuration, and gathers every voter
you registered. Build it by hand only in a test.

## Strategies

`AccessDecisionManagerConfig(strategy=…, allow_if_all_abstain=False, allow_if_equal_granted_denied=True)`.

| `strategy` | Grants when |
| --- | --- |
| `"affirmative"` (default) | any voter grants |
| `"consensus"` | grants outnumber denials; a tie follows `allow_if_equal_granted_denied` |
| `"unanimous"` | no voter denies |
| `"priority"` | the first voter that does not abstain grants |

A decision every voter abstained on is refused unless `allow_if_all_abstain=True`. Under the
affirmative default, one voter that grants too eagerly decides everything — which is why a
voter's `supports` must be narrow.

## The built-in voters

| Voter | Grants on |
| --- | --- |
| `RoleHierarchyVoter(hierarchy)` | a role the token's roles *reach* through the hierarchy |
| `RoleVoter()` | a role the token holds outright |
| `AuthenticatedVoter(trust_resolver)` | `IS_AUTHENTICATED_VERY_RECENTLY`, `IS_AUTHENTICATED_RECENTLY`, `IS_AUTHENTICATED_FULLY`, `IS_AUTHENTICATED_REMEMBERED`, `IS_AUTHENTICATED`, `IS_REMEMBERED`, `IS_IMPERSONATOR` (never, as yet), `PUBLIC_ACCESS` asked alone |
| `OAuth2ScopeVoter()` | an `OAUTH2_SCOPE(...)` attribute every scope of which the token holds |
| `ClosureVoter()` | a callable attribute `(IsGrantedContext, subject) -> bool` returning `True` |

The bundle registers all five and adds yours. `PUBLIC_ACCESS` is how an access-control rule says
"open": it grants whether or not anybody is authenticated.

The recency attributes read the token's authentication proofs —
`token.set_authentication_proofs({AuthenticationMethod.PASSWORD: timestamp})` — against the trust
resolver's windows (two hours, five minutes); a denied one requests a re-authentication on its
vote. Asking an authentication attribute through `is_granted_for_user` raises
`InvalidArgumentError`: how that user authenticated is unknown.

## Your voter

Extend `Voter` and answer two methods; `@as_service` is all the wiring.

```python
def supports(self, attribute: object, subject: object) -> bool: ...
async def vote_on_attribute(
    self, attribute: object, subject: object, token: TokenInterface, vote: Vote | None
) -> bool: ...
```

- `supports` is asked per attribute and subject. Return `False` for anything you do not own; the
  voter then abstains and the others decide.
- `vote` is the record of this voter's answer; `vote.add_reason("...")` explains a refusal and
  shows up in the `AccessDecision` a handler can read.
- A voter is a service like any other: inject a repository, a clock, a logger.
- `CacheableVoterInterface` additionally declares `supports_attribute` / `supports_type` so the
  manager can skip a voter that could never speak.

A one-off rule needs no class at all:

```python
from xtr_security_core import IsGrantedContext


async def can_publish(context: IsGrantedContext, subject: object) -> bool:
    return await context.is_granted("ROLE_ADMIN")


@router.post("/books/{isbn}/publish")
@IsGranted(can_publish)
async def publish(isbn: str) -> None: ...
```

`IsGrantedContext` carries the `token`, its `user`, `is_granted(...)` for a nested question —
decided for the same token, its reasons reported on the closure's vote — and the
`is_authenticated()`, `is_authenticated_fully()`, `is_authenticated_recently()`,
`is_authenticated_very_recently()` and `is_impersonator()` shortcuts.

## The role hierarchy

`role_hierarchy={"ROLE_ADMIN": ("ROLE_USER",)}` makes an admin reach the user role, so a token
needs only the role it really has. Expansion is transitive and safe against cycles. A `*` in a key
captures a segment and substitutes it into the values, so
`{"ROLE_TENANT_*_ADMIN": ("ROLE_TENANT_*_USER",)}` makes `ROLE_TENANT_42_ADMIN` reach
`ROLE_TENANT_42_USER`.

Standalone, `RoleHierarchy(mapping).get_reachable_role_names(roles)` is the same expansion.
`get_parent_role_names(roles)` asks the inverse: every declared role that reaches one of them.

## OAuth2 scopes

A scope requirement is an attribute like any other. `oauth2_scope("books:read", "books:write")`
builds `"OAUTH2_SCOPE(books:read books:write)"`, which goes in an `AccessControlConfig` or an
`IsGranted`; `parse_oauth2_scope(attribute)` — from `xtr_security_http.authorization` — reads the
scopes back, or `None` for anything not shaped like one.

On a route, write the scope as the access rule that matches it:

```python
@configure
def security() -> SecurityConfig:
    return SecurityConfig(
        firewalls={"api": FirewallConfig(pattern=r"^/api")},
        access_control=(
            AccessControlConfig(path=r"^/api/books", attribute=oauth2_scope("books:read")),
        ),
    )
```

An access-token authenticator copies the badge's granted `scope` onto the token, and
`OAuth2ScopeVoter` reads it; a refused scope is answered `403` with an RFC 6750
`insufficient_scope` challenge.

## Reading a decision

`is_granted(attribute, subject=None, access_decision=None)` fills an `AccessDecision` when given
one: every `Vote` cast, each with its `voter`, `result` and `reasons`, the deciding strategy's
name (`"affirmative"`, …) and a `message`. `deny_access_unless_granted(...)` attaches one to the `AccessDeniedError` it
raises, which is how a handler can tell a caller *why*. With `trace_votes` on (the default in
debug) each vote is also announced as a `VoteEvent` a listener can log, and the request's
`AccessDecisionManagerInterface` is a `TraceableAccessDecisionManager` whose
`get_decision_log()` lists every decision with its votes.
