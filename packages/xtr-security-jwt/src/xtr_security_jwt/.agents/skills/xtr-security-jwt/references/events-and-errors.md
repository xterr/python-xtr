# Events and errors

## Events

Every event has a name constant on `Events` (`from xtr_security_jwt import Events`). A listener
names the constant; it never imports the event class only to name it.

| Name | Dispatched | A listener may |
| --- | --- | --- |
| `Events.JWT_CREATED` | Before a token is signed | Shape the claims and the header |
| `Events.JWT_ENCODED` | After a token is signed | Observe the finished token |
| `Events.JWT_DECODED` | After a token verifies | Reject it |
| `Events.JWT_AUTHENTICATED` | After a token authenticated a request | Observe the payload |
| `Events.JWT_EXPIRED` | An expired token is refused | Observe, or shape the response |
| `Events.JWT_INVALID` | A bad token is refused | Observe, or shape the response |
| `Events.JWT_NOT_FOUND` | A protected request carried no token | Observe, or shape the response |
| `Events.AUTHENTICATION_SUCCESS` | A token is issued to a client | Add to the response data |
| `Events.AUTHENTICATION_FAILURE` | A token authentication failed | Shape the response |

Prefer a `PayloadEnrichmentInterface` over a `JWT_CREATED` listener when all you do is add a
claim to every token: it is one object with one job, and it needs no dispatcher.

## Errors

Import from `xtr_security_jwt.exception`. All derive from `SecurityError`
(`xtr_security_core.exception`), so one `except SecurityError` catches every one.

| Error | Base | Raised when |
| --- | --- | --- |
| `JwtFailureError` | `SecurityError` | The base of the signing and verification failures; carries a `reason` and any decoded `payload` |
| `JwtEncodeFailureError` | `JwtFailureError` | A token could not be signed: reason `invalid_config` or `unsigned_token` |
| `JwtDecodeFailureError` | `JwtFailureError` | A token could not be read: reason `invalid_token`, `expired_token` or `unverified_token` |
| `MissingClaimError` | `JwtFailureError` | A token lacks a claim a caller required |
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
- `InvalidConfigurationError` (`xtr_security.bundle`) at build time, when no `secret_key` is
  configured. It names the missing setting and the config function to write.
