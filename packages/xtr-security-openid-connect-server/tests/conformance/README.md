# Conformance suite

One module per part of OpenID Connect this provider follows: OpenID Connect
Core 1.0 for the authorization code flow — the ID token, the authentication
request, the userinfo endpoint, refresh — and OpenID Connect Discovery 1.0.
Every test names the requirement it answers for in a comment above its
assertions, so a reader can go from a requirement to the test and back.

Each test drives a real served deployment — the fixture `tests/fixtures/openid_app`,
both bundles listed, in the environment the requirement is about — and checks
what a client receives with the repository's own relying party, which shares no
code with the provider:

- `tests/support/relying_party.py` reads the served configuration document,
  key set and userinfo answer through the discovery reader, the signature
  verifier (strict key usage: only keys marked for signatures verify) and the
  ID-token claim checks of `xtr-security-http`.
- `tests/support/relying_party_login.py` serves a second application, with a
  kernel of its own (`tests/fixtures/relying_party_app`), whose firewall signs
  its users in with `xtr-security-http`'s OpenID Connect login. The login
  reaches the provider live over ASGI, so one test makes a whole sign-in as a
  client application makes it: authorization request, code, token exchange,
  signature and claim checks, userinfo, the user loaded.

What `at_hash` must equal is computed in the test from the access token the
answer carries (the relying party does not check it); the published vectors
are in `tests/unit/test_token_hash.py`.

## Modules

| Module | Standard | Tests | Gaps |
|---|---|---|---|
| `test_oidc_core_id_token.py` | Core 1.0 § 2, § 3.1.3.3, § 3.1.3.6, § 3.1.3.7, § 10.1, § 15.1 — the ID token | 19 | — |
| `test_oidc_core_authentication_request.py` | Core 1.0 § 3.1, § 3.1.2, § 3.1.3.2, § 15.1 — the authentication request, `prompt`, `max_age` | 14 | 2 |
| `test_oidc_core_userinfo.py` | Core 1.0 § 5.3, § 5.4 — the userinfo endpoint | 11 | — |
| `test_oidc_core_refresh.py` | Core 1.0 § 12 — refresh | 2 | — |
| `test_oidc_discovery.py` | Discovery 1.0 § 3, § 4 — the configuration document | 15 | — |

A gap is a requirement this provider does not meet: its test is written as
the standard reads and marked `xfail(strict=True)`, so meeting the requirement
turns the mark into a failure and the mark is removed in the same change. The
*deliberate deviations* at the end of this file are a different thing: each is
a decision recorded for this provider, pinned by the test named.

## OpenID Connect Core 1.0

| § | Requirement | Covered by |
|---|---|---|
| 2 | `iss` is an `https` URL with no query or fragment | `test_the_issuer_is_an_https_url_with_no_query_and_no_fragment` (ID token) |
| 2 | `sub` MUST NOT exceed 255 ASCII characters | `test_the_subject_is_ascii_and_at_most_255_characters` |
| 2 | `aud` MUST contain the client's `client_id` | `test_the_audience_is_the_client_that_asked` |
| 2 | `exp` and `iat` are required, the token expiring after it was issued | `test_the_token_expires_after_it_was_issued`; the relying party's time checks in `test_the_relying_party_accepts_the_id_token` |
| 2 | A `nonce` sent MUST be returned unmodified in the ID token | `test_the_nonce_the_request_sent_is_claimed_unmodified`, `test_no_nonce_is_claimed_when_the_request_sent_none`, `test_two_codes_redeemed_at_once_each_carry_their_own_nonce` |
| 2 | ID tokens MUST be signed with JWS, never `none` | `test_the_token_is_signed_with_a_real_algorithm`, `test_an_id_token_changed_by_one_character_is_refused` |
| 2 | No `x5u`, `x5c`, `jku` or `jwk` header (SHOULD NOT) | `test_the_header_carries_no_key_by_value_or_by_reference` |
| 3.1 | The authorization code flow, end to end, against a client implementation | `test_a_client_application_signs_its_user_in_with_the_provider` |
| 3.1.2.1 | The authorization endpoint MUST support `GET` | `test_the_authorization_endpoint_answers_a_get` |
| 3.1.2.1 | The authorization endpoint MUST support `POST`, its parameters form-serialized | **gap** — `test_the_authorization_endpoint_answers_a_posted_form` |
| 3.1.2.1 | `redirect_uri` is REQUIRED | **gap** — `test_a_request_naming_no_redirect_uri_is_refused` |
| 3.1.2.1 | `prompt=none`: no page shown, an error when nobody is signed in | `test_prompt_none_with_nobody_signed_in_is_refused_at_the_redirect_uri`, `test_prompt_none_with_the_end_user_signed_in_goes_on_to_the_code` |
| 3.1.2.1 | `none` with any other value is an error | `test_prompt_none_beside_another_value_is_refused` — answered as a document, see the deviations |
| 3.1.2.1 | `prompt=login` re-authenticates (SHOULD) | `test_prompt_login_has_a_signed_in_end_user_sign_in_again` |
| 3.1.2.1 | `prompt=consent`, and `consent_required` when consent cannot be asked for | the application's consent listener, reading the prompt through `OpenIdAuthorizationRequest.get_prompt()`; the refusal it raises is `consent_required(event)`, covered by `tests/unit/test_prompt.py::test_each_refusal_is_catalogued_under_a_number_of_its_own` and `test_a_refusal_is_delivered_to_the_redirect_uri_carrying_the_state` |
| 3.1.2.1 | `max_age`: the ID token MUST include `auth_time` | `test_max_age_has_the_id_token_state_when_the_end_user_signed_in` |
| 3.1.2.1 | `max_age` exceeded: the OP MUST actively re-authenticate | `test_a_sign_in_older_than_max_age_is_made_again` |
| 3.1.2.2 | The server MUST validate the OAuth 2.0 parameters | the provider's flow extends the authorization server's own; RFC 6749 is covered by `xtr-security-oauth2-server`'s `tests/conformance/test_rfc6749_authorization_framework.py` |
| 3.1.2.6 | An error goes to the redirect URI with `state`, unless the redirect URI is invalid | `test_prompt_none_with_nobody_signed_in_is_refused_at_the_redirect_uri`, `test_a_refusal_about_the_redirect_uri_is_never_a_redirect` |
| 3.1.3.2 | Client authentication, the code issued to that client, used once, the identical `redirect_uri` | `xtr-security-oauth2-server`'s RFC 6749 module: `test_a_confidential_client_must_authenticate_to_redeem_a_code`, `test_a_code_cannot_be_redeemed_by_another_client`, `test_a_code_used_a_second_time_is_denied`, `test_a_code_is_redeemed_only_against_the_redirect_uri_it_was_tied_to` |
| 3.1.3.2 | An ID token only for a code issued to an OpenID Connect request | `test_a_code_issued_for_a_request_without_openid_earns_no_id_token` |
| 3.1.3.3 | The token response to a sign-in carries the `id_token` | `test_the_token_answer_to_a_sign_in_carries_an_id_token` |
| 3.1.3.3 | `Cache-Control: no-store` (and `Pragma: no-cache`) | `test_the_token_answer_may_not_be_cached` |
| 3.1.3.6 | `at_hash`: the left half of the hash of the access token, by the `alg`'s hash | `test_the_at_hash_is_the_left_half_of_the_access_tokens_hash` |
| 3.1.3.7 | The ID token passes a client's validation: signature, `iss`, `aud`, time, `nonce` | `test_the_relying_party_accepts_the_id_token`, `test_a_token_signed_with_rs256_is_accepted_by_the_relying_party` |
| 5.3.1 | The userinfo endpoint MUST support `GET` and `POST` | `test_the_endpoint_answers_a_get_carrying_a_bearer_token`, `test_the_endpoint_answers_a_post_carrying_a_bearer_token` |
| 5.3.1 | It MUST accept access tokens as RFC 6750 bearer tokens | the two above, in the `Authorization` header; the form-body method is a deviation, see below |
| 5.3.2 | `sub` MUST always be returned | `test_the_subject_is_always_answered` |
| 5.3.2 | The `sub` answered matches the ID token's (the client MUST check) | `test_the_subject_answered_is_the_one_the_id_token_names` |
| 5.3.2 | A content type names the format: JSON | `test_the_answer_is_a_json_object` |
| 5.3.3 | Errors as RFC 6750 § 3: a `Bearer` challenge, `invalid_token`, `insufficient_scope` | `test_a_request_carrying_no_token_is_refused_with_a_challenge`, `test_a_token_not_granted_openid_is_refused_as_insufficient`, `test_a_token_naming_no_end_user_is_refused` |
| 5.4 | `profile`, `email`, `address`, `phone` reveal their claims at the userinfo endpoint | `test_the_scopes_granted_reveal_their_claims`, `test_a_claim_of_a_scope_not_granted_is_not_revealed` |
| 5.4 | Those claims are the userinfo endpoint's, not the ID token's (a decision, N7) | `test_the_id_token_claims_who_signed_in_and_nothing_a_scope_reveals` |
| 10.1 | With several keys published, the header MUST carry a `kid` | `test_the_token_names_the_published_key_it_was_signed_with` |
| 10.1 | The key verifies from the published set, read with strict key usage | `test_a_verifier_checking_key_usage_strictly_keeps_every_published_key` |
| 12.2 | A refresh answers a token response that might not contain an `id_token` | `test_a_refresh_is_answered_with_a_new_access_token`, `test_a_refresh_is_answered_without_an_id_token` |
| 15.1 | Signing ID tokens with `RS256` | `test_a_token_signed_with_rs256_is_accepted_by_the_relying_party` |
| 15.1 | The `prompt` parameter | the `prompt` rows of § 3.1.2.1 above |
| 15.1 | `display`, `ui_locales`, `acr_values`: their use must not result in an error | `test_parameters_asking_for_a_presentation_are_ignored_without_error` |
| 15.1 | `auth_time` when requested, and `max_age` enforced | the `max_age` rows of § 3.1.2.1 above |

The issuer is the deployment's own, never the request's `Host`:
`test_the_issuer_does_not_follow_the_host_the_request_names`.

## OpenID Connect Discovery 1.0

| § | Requirement | Covered by |
|---|---|---|
| 3 | `issuer`: `https`, no query or fragment | `test_the_issuer_is_an_https_url_with_no_query_and_no_fragment` (discovery) |
| 3 | `issuer`, `authorization_endpoint`, `token_endpoint`, `jwks_uri`, `response_types_supported`, `subject_types_supported`, `id_token_signing_alg_values_supported` are REQUIRED | `test_every_required_field_is_published` |
| 3 | `userinfo_endpoint` MUST use `https` | `test_the_endpoints_are_https_urls_under_the_issuer` |
| 3 | `RS256` MUST be among `id_token_signing_alg_values_supported` | `test_rs256_is_among_the_id_token_signing_algorithms` — met by a deployment signing with `RS256`, see the deviations |
| 3 | The server MUST support the `openid` scope | `test_the_openid_scope_is_supported` |
| 3 | `response_types_supported`, `subject_types_supported` | `test_the_code_flow_is_the_response_type_published`, `test_public_subject_identifiers_are_published` |
| 3 | `claims_supported`, `claims_parameter_supported`, `request_parameter_supported`, `request_uri_parameter_supported` | `test_the_claims_published_include_every_claim_an_id_token_carries`, `test_the_parameters_the_provider_does_not_read_are_published_unsupported` |
| 3 | The key set MUST NOT contain private or symmetric keys | `test_the_key_set_holds_no_private_or_symmetric_key` |
| 3 | A `use` is REQUIRED for every key when both kinds are published | `test_every_published_key_names_its_use` — only signing keys are published, each marked `sig` |
| 4 | The document MUST be at `/.well-known/openid-configuration` under the issuer | `test_the_document_is_served_under_the_issuer_at_the_well_known_path` |
| 4.2 | `200 OK`, a JSON object, `application/json` | `test_a_successful_answer_is_two_hundred_and_json` |
| 4.2 | Claims with zero elements MUST be omitted | `test_a_field_with_nothing_in_it_is_left_out` |
| 4.3 | The `issuer` returned MUST be identical to the one the document was read under | `test_the_issuer_published_is_the_one_the_document_was_read_under` |

## Not covered, by decision

Each requirement below belongs to a feature outside this provider's scope —
decision N3 (OpenID Connect Core 1.0, authorization code flow only) or the
plan's *Must NOT have* list — so there is no test of it.

- **The implicit and hybrid flows** (Core § 3.2, § 3.3): an `id_token` from the
  authorization endpoint, `c_hash`, `at_hash` on the authorization response,
  the fragment response mode. *Must NOT*: no implicit or hybrid response types.
- **Logout and session management** (Session Management, Front-Channel,
  Back-Channel and RP-Initiated Logout; `end_session_endpoint`). *Must NOT*: no
  logout of any kind.
- **The `claims` request parameter** (Core § 5.5), including `auth_time`
  requested as an essential claim. *Must NOT*; published
  `claims_parameter_supported: false`.
- **Request objects** (Core § 6, `request` and `request_uri`). *Must NOT*;
  published unsupported.
- **Pairwise subject identifiers** (Core § 8.1). *Must NOT*; only `public` is
  published.
- **`acr` and `amr`** (Core § 2, § 3.1.2.1 `acr_values`). *Must NOT* beyond
  ignoring the parameter — the § 15.1 minimum, which is tested.
- **`offline_access`** (Core § 11). *Must NOT*.
- **Dynamic client registration** and what Core § 15.2 asks of a dynamic
  provider (the `id_token` response types, `request_uri`). *Must NOT*.
- **Encrypted ID tokens and signed or encrypted userinfo answers** (Core
  § 10.2, § 5.3.2). Outside N3: ID tokens are signed only, and the userinfo
  answer is plain JSON, which § 5.3.2 makes the answer for a client that
  registered no other.
- **An ID token on refresh** (Core § 12.2). *Must NOT*; the omission the
  section permits is tested.
- **Client authentication methods** (Core § 9). The authorization server's;
  its own suite covers the methods it supports.
- **`sub` locally unique and never reassigned** (Core § 2). The identity
  provider's, which the application writes.
- **Transport security** (Core § 16.17, Discovery § 7.1). The deployment's: no
  test can assert TLS of an application served over ASGI.
- **CSRF and clickjacking protection of the login page** (Core § 3.1.2.3). The
  application's, which owns the page.
- **Client-side requirements** (Core § 3.1.3.7, § 3.1.2.7, Discovery § 4.3's
  "MUST NOT be used"): the client's to meet. The relying party used here meets
  them, which is what makes it an oracle.

## Deliberate deviations

| Where | This provider | The standard | Why |
|---|---|---|---|
| `prompt=none` beside another value | `400 invalid_request`, answered as a document | Core § 3.1.2.1 says "an error is returned"; RFC 6749 § 4.1.2.1 would send it to the redirect URI | Recorded decision: the request is malformed before it is validated as a sign-in. `test_prompt_none_beside_another_value_is_refused` |
| `prompt=select_account` | `400 invalid_request` | Core § 3.1.2.1 defines it, with `account_selection_required` when no choice can be made | Outside N3, which names `none`, `login` and `consent`; refused rather than ignored, so a client never carries on believing it was honoured. `test_prompt_select_account_is_refused` |
| The access token in the userinfo request's form body | not read; `401 invalid_token` | Core § 5.3.1 allows any RFC 6750 § 2 method, § 2.2 being the form-encoded body | Recorded user decision: the token is read from the `Authorization` header only. `test_a_token_carried_in_the_form_body_alone_is_not_read` |
| `RS256` in `id_token_signing_alg_values_supported` | the one algorithm the deployment signs with | Discovery § 3 requires `RS256` to be listed | The ID token is signed with the authorization server's own key and algorithm (N6, N20), `RS256` by default. A deployment configured for another algorithm — the `ES256` fixture deployment — publishes only that one. `test_rs256_is_among_the_id_token_signing_algorithms` reads an `RS256` deployment |

## An optional manual run of the OpenID Foundation conformance suite

The OpenID Foundation publishes a conformance suite for providers. Running it
is optional, manual and outside CI; its outcome is not a claim this repository
makes, and nothing here states that this provider passed it.

To run it against a deployment of this package:

1. Serve the deployment over HTTPS at a public issuer — the suite reaches the
   provider from its own servers — with the authorization server signing with
   `RS256`, the `openid`, `profile`, `email`, `address` and `phone` scopes
   available, an identity provider configured, and `/userinfo` behind the
   access tokens' firewall.
2. Register two confidential clients for the suite, with the redirect URIs it
   names, and the login page reachable for a test user.
3. In the suite's web interface, create a test plan from
   `oidcc-basic-certification-test-plan`, with server metadata `discovery`,
   client registration `static_client`, the issuer, and both clients.
4. Run the modules one by one, signing in as the test user when the suite asks.

Expect the modules for what this file records as gaps, deviations or out of
scope to fail or be skipped: `POST` to the authorization endpoint, a missing
`redirect_uri`, `prompt=none` beside another value, the form-body token at the
userinfo endpoint, and anything needing the `claims` or `request` parameters.
