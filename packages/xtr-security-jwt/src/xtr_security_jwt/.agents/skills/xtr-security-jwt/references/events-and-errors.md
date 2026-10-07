# Events and errors

## Events

Every event is dispatched as itself, never under a separate name. A listener subscribes to the
class it reads, imported from `xtr_security_jwt.event`.

| Event | Dispatched | A listener may |
| --- | --- | --- |
| `JwtCreatedEvent` | Before a token is signed | Shape the claims and the header |
| `JwtEncodedEvent` | After a token is signed | Observe the finished token |
| `JwtDecodedEvent` | After a token verifies | Reject it |
| `JwtAuthenticatedEvent` | After a token authenticated a request | Observe the payload |
| `JwtExpiredEvent` | An expired token is refused | Observe, or shape the response |
| `JwtInvalidEvent` | A bad token is refused | Observe, or shape the response |
| `JwtNotFoundEvent` | A protected request carried no token | Observe, or shape the response |

Those seven are everything this package dispatches. The last three derive from
`AuthenticationFailureEvent`, which is never dispatched on its own: a listener that handles any
refusal subscribes to that base — or to the `JwtFailureEventInterface` it implements — instead of
to all three.

```python
from collections.abc import Mapping

from xtr_event_dispatcher import EventSubscriberInterface, SubscribedEvents

from xtr_security_jwt.event.jwt_decoded_event import JwtDecodedEvent


class RefuseRevoked(EventSubscriberInterface):
    @classmethod
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {JwtDecodedEvent: "on_decoded"}

    async def on_decoded(self, event: JwtDecodedEvent) -> None:
        if event.get_payload().get("jti") == "revoked":
            event.mark_as_invalid()
```

Prefer a `PayloadEnrichmentInterface` over a `JwtCreatedEvent` listener when all you do is add a
claim to every token: it is one object with one job, and it needs no dispatcher.

## Errors

Import from `xtr_security_jwt.exception`. All derive from `SecurityError`
(`xtr_security_core.exception`), so one `except SecurityError` catches every one.

| Error | Base | Raised when |
| --- | --- | --- |
| `JwtFailureError` | `SecurityError` | The base of the signing and verification failures; carries a `reason` and any decoded `payload` |
| `JwtEncodeFailureError` | `JwtFailureError` | A token could not be signed: reason `invalid_config` or `unsigned_token` |
| `JwtDecodeFailureError` | `JwtFailureError` | A token could not be read: reason `invalid_token`, `expired_token` or `unverified_token` |
| `ExpiredTokenError` | `AuthenticationError` | A caller presented an expired token; answered `401` "Expired JWT Token" |
| `InvalidTokenError` | `AuthenticationError` | A malformed, unsigned or tampered token; `401` "Invalid JWT Token" |
| `MissingTokenError` | `AuthenticationError` | A protected request carried no token; `401` "JWT Token not found" |
| `InvalidPayloadError` | `AuthenticationError` | A verified token carried no user-id claim |

The four `AuthenticationError` ones are the firewall's answers to a request: it turns them into
the `401` itself, so an application rarely catches them. The `JwtFailureError` family is what
`tokens.create` and `tokens.parse` raise at you.

Two more come from outside the family:

- `InvalidArgumentError` (`xtr_security_core.exception`) for a `JwtConfig` the library will not
  accept, or an algorithm it will not sign with.
- `InvalidConfigurationError` (`xtr_security.bundle`) at build time: when `secret_key` or
  `issuer` is unset — it names the missing setting and the config function to write — or when an
  `HS*` secret is shorter than the algorithm's floor.
