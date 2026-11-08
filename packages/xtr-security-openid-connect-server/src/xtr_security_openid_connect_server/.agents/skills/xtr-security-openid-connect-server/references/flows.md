# Flows

What a sign-in does end to end, and what each request parameter changes.

## The authorization code flow, with `openid`

1. The client sends the browser to `authorize_path` with `response_type=code`, `client_id`,
   `redirect_uri`, `scope` containing `openid`, and usually `state`, `nonce`, `code_challenge` and
   `code_challenge_method`. `GET` and a form-encoded `POST` both work.
2. The login firewall's chain runs. The prompt step acts there when the request carries `prompt` or
   `max_age`, and nothing else does.
3. `OpenIdAuthCodeGrant.validate_authorization_request` reads the shipped request first — an
   unknown client or an unregistered redirect is refused as it always was — then `nonce`, `prompt`
   and `max_age`. A request asking for `openid` and naming no `redirect_uri` is `invalid_request`,
   answered as a document, because it named nowhere to send a refusal.
4. `OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE` is dispatched. `stamp_auth_time` records the
   sign-in time at priority `2048`; the application's consent listener, below it, approves, denies
   or answers a page.
5. The code is minted with the `nonce` and the sign-in time sealed into it beside what the shipped
   flow seals, and the browser goes back to the redirect URI.
6. The client redeems the code at `/token`. The shipped half runs first, so an unreadable, expired,
   spent or another client's code is refused in the protocol's own words. Then the sign-in is read
   back out of the code and handed to the answer.
7. The answer is the bearer answer plus `id_token`, signed with the authorization server's key and
   `kid`.

## What the ID token carries

| Claim | From |
|---|---|
| `iss` | `authorization_server.issuer` |
| `sub` | The resource owner's identifier, as the code named it |
| `aud` | The client's identifier, as a string |
| `iat` | The clock, when the answer is built |
| `exp` | `iat + id_token_ttl`, or the access token's own expiry when that setting is unset |
| `auth_time` | The newest authentication proof on the firewall's token at the authorization endpoint. Omitted when unknown |
| `nonce` | The `nonce` the authorization request carried. Omitted when it carried none |
| `at_hash` | The left half of the digest of the access token string answered beside it, base64url without padding, under the digest the `alg` signs with — for `EdDSA`, the one its key's curve signs with: SHA-512 over Ed25519, 114 octets of SHAKE256 over Ed448 |

Nothing else. `name`, `email`, `address` and `phone_number` are `/userinfo`'s, never the ID token's.

An ID token is answered only when the grant handed the answer an identity **and** the granted
scopes contain `openid`. The refresh grant hands none, so a refresh answer never carries one.

## `prompt`

Read as a space-separated set. A value this server does not act on, and `none` beside any other
value, are `invalid_request` — refused rather than ignored, so a client never carries on believing
it was honoured. `select_account` is therefore refused too.

| Value | Nobody signed in | Signed in |
|---|---|---|
| (none) | The endpoint's own `access_denied`, or whatever the login firewall does | The flow goes on |
| `none` | `login_required` at the validated redirect URI, with `state` echoed back | The flow goes on; the consent listener raises `consent_required(event)` if consent is still needed |
| `login` | Redirect to `login_path` | Redirect to `login_path` — they sign in again |
| `consent` | The login firewall's business; then the consent listener's | The consent listener shows its page |

## `max_age`

A whole number of seconds, zero or more; anything else is `invalid_request`.

The sign-in's age is the newest authentication proof on the firewall's token, measured against the
injected clock. A token that proves nothing — a remembered login — has no known sign-in time, so it
is never fresh enough for any `max_age`.

| State | Outcome |
|---|---|
| Fresh enough | The flow goes on; the ID token states `auth_time` |
| Too old, or unknown | A re-login: redirect to `login_path`, the request parked |
| Too old with `prompt=none` | `login_required` — no page may be shown |

## The re-login round trip

`prompt=login`, or an exceeded `max_age`, parks the authorization request in the login firewall's
session and answers a `302` to `login_path`:

1. The request kept is the original one with `login` taken out of `prompt`, and `prompt` dropped
   when nothing is left in it — so the return trip goes on to the code instead of asking again. A
   request that arrived as a posted form is kept as the `GET` the return trip makes.
2. The end-user signs in on the login page. The firewall sends them back to the parked path.
3. The chain runs again. `prompt` no longer asks for a re-login, the sign-in is new, and the flow
   goes on.

The firewall must keep a session for step 1. A stateless one raises `InvalidConfigurationError`
naming `stateless`, the firewall and `login_firewall`.

## `/userinfo`

| Request | Answer |
|---|---|
| `GET` or form `POST` with a bearer token granted `openid`, naming an end-user | `200`, `application/json`, `cache-control: no-store`, `{"sub": …, **claims}` |
| No token, or a token this server did not issue | `401` `invalid_token`, with a `Bearer` challenge |
| A client-credentials token, whose caller names no end-user | `401` `invalid_token` |
| A token not granted `openid` | `403` `insufficient_scope` |
| A `POST` whose body is not form-encoded | `400` `invalid_request` |

`sub` is answered first and is the identifier the ID token named, so a client can compare them; no
claim of the identity provider's replaces it, not even one called `sub`. The token is read from the
`Authorization` header only — a token in the form body alone is not read.
