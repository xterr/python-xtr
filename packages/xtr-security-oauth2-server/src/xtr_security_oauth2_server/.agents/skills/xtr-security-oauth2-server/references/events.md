# Events

Every event is dispatched **under a name**, and a listener registers under the very same name:
`@as_event_listener(OAuth2Events.X)` from `xtr_event_dispatcher`. Registering under the event
class instead reaches nothing, silently. The dispatcher reads a listener's annotation at runtime,
so import the event class at module level, never under `TYPE_CHECKING`.

## The bundle's six (`xtr_security_oauth2_server.oauth2_events.OAuth2Events`)

| Name | Event (`xtr_security_oauth2_server.event.…`) | What a listener does |
| --- | --- | --- |
| `AUTHORIZATION_REQUEST_RESOLVE` | `AuthorizationRequestResolveEvent` | `resolve_authorization(APPROVED or DENIED)`, or `set_response(page)`; either stops later listeners. Denied until resolved |
| `SCOPE_RESOLVE` | `ScopeResolveEvent` | `set_scopes(*scopes)` — the last word on what a token carries; `get_grant()`, `get_client()`, `get_user_identifier()` |
| `USER_RESOLVE` | `UserResolveEvent` | The password grant only: check `get_username()` / `get_password()`, `set_user(user)`; unset refuses |
| `ACCESS_TOKEN_EXTRA_CLAIMS_RESOLVE` | `AccessTokenExtraClaimsResolveEvent` | `set_extra_claims({...})` signed into the token; the token's own claim names are refused |
| `TOKEN_REQUEST_RESOLVE` | `TokenRequestResolveEvent` | `set_response(...)` replacing the token answer, refusals included |
| `PRE_SAVE_CLIENT` | `PreSaveClientEvent` | Change `get_client()`, or `set_client(other)`, before a manager stores it |

```python
from xtr_event_dispatcher import as_event_listener
from xtr_security_oauth2_server.event.access_token_extra_claims_resolve_event import (
    AccessTokenExtraClaimsResolveEvent,
)
from xtr_security_oauth2_server.event.pre_save_client_event import PreSaveClientEvent
from xtr_security_oauth2_server.event.scope_resolve_event import ScopeResolveEvent
from xtr_security_oauth2_server.event.token_request_resolve_event import TokenRequestResolveEvent
from xtr_security_oauth2_server.oauth2_events import OAuth2Events


@as_event_listener(OAuth2Events.SCOPE_RESOLVE)
async def no_writes_for_services(event: ScopeResolveEvent) -> None:
    if event.get_user_identifier() is None:  # a client acting for itself
        _ = event.set_scopes(
            *(scope for scope in event.get_scopes() if str(scope) != "invoices:write")
        )


@as_event_listener(OAuth2Events.ACCESS_TOKEN_EXTRA_CLAIMS_RESOLVE)
async def add_tenant(event: AccessTokenExtraClaimsResolveEvent) -> None:
    _ = event.set_extra_claims({"tenant": "acme"})


@as_event_listener(OAuth2Events.TOKEN_REQUEST_RESOLVE)
async def mark_the_answer(event: TokenRequestResolveEvent) -> None:
    _ = event.set_response(event.get_response().with_header("x-issued-by", "invoicing"))


@as_event_listener(OAuth2Events.PRE_SAVE_CLIENT)
async def deactivate_untrusted(event: PreSaveClientEvent) -> None:
    client = event.get_client()
    if client.get_name().startswith("Untrusted"):
        _ = client.set_active(False)
```

The password grant's user check:

```python
from xtr_event_dispatcher import as_event_listener
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_oauth2_server.event.user_resolve_event import UserResolveEvent
from xtr_security_oauth2_server.oauth2_events import OAuth2Events


@as_event_listener(OAuth2Events.USER_RESOLVE)
async def resolve_user(event: UserResolveEvent) -> None:
    if event.get_username() != "ada" or event.get_password() != "the-password":  # check a hash
        return
    _ = event.set_user(InMemoryUser("ada", roles=["ROLE_USER"]))
```

The shipped `AddClientDefaultScopesListener` is the `PRE_SAVE_CLIENT` listener that gives a
client registered with no scopes `scopes.default`.

## Consent, in two passes

The first pass answers the browser with a page; the form posts the original query back to
`/authorize`; the second pass approves. Nothing is remembered between them, so the listener tells
them apart from the request — a field of its form — and must check a CSRF token bound to
`event.get_user()` before approving. `event.is_authorization_approved()` reports the request's own
flag, `event.get_scopes()` the stored scopes asked for, `event.get_client()` the stored client.

## The protocol library's five (`xtr_security_oauth2_server_core.request_event.RequestEvent`)

| Name | Event | When |
| --- | --- | --- |
| `ACCESS_TOKEN_ISSUED` | `RequestAccessTokenEvent` (`get_access_token()`) | Any grant issued an access token |
| `REFRESH_TOKEN_ISSUED` | `RequestRefreshTokenEvent` | A refresh token was issued |
| `CLIENT_AUTHENTICATION_FAILED` | `RequestEvent` | A client failed to authenticate |
| `USER_AUTHENTICATION_FAILED` | `RequestEvent` | The password grant refused a user |
| `REFRESH_TOKEN_CLIENT_FAILED` | `RequestEvent` | A refresh token came from another client |

Each carries `get_name()` and `get_request()`.

```python
from xtr_event_dispatcher import as_event_listener
from xtr_security_oauth2_server_core.request_access_token_event import RequestAccessTokenEvent
from xtr_security_oauth2_server_core.request_event import RequestEvent


@as_event_listener(RequestEvent.ACCESS_TOKEN_ISSUED)
async def audit(event: RequestAccessTokenEvent) -> None:
    print("issued to", event.get_access_token().get_client().get_identifier())
```

Count `CLIENT_AUTHENTICATION_FAILED` to throttle a client guessing secrets.
