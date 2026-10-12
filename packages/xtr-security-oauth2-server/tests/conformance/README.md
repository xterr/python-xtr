# Conformance suite

One module per standard this authorization server claims to follow. Every test
names the section it answers for in a comment above its assertions, so a reader
can go from a requirement to the test and back.

Where a standard says what a client receives, the test drives a real served
application — the router this package ships, mounted on an application whose
container the kernel built — and asserts on the answer. Where a standard fixes
a *value* rather than an exchange, the test reads that value directly: the
derivation of a proof key, the claims a token carries, the alphabet a user code
is drawn from.

## Where the cases come from

Each case answers a requirement of the standard its module is named after. Where one was taken
from another implementation's suite, the test says which:

| Source | Pin |
|---|---|
| `oauthlib` | `v4.0.0` @ `145a9a4690cb4d9de30d15fcc2984e34c49df741` |
| `aioauth` | `2.0.1` @ `81365d30a5e4bf8ec48490032b73e1728b359570` (test vectors only) |

## Modules

| Module | Standard | Tests | Gaps |
|---|---|---|---|
| `test_rfc6749_authorization_framework.py` | RFC 6749 — The OAuth 2.0 Authorization Framework | 29 | — |
| `test_rfc6750_bearer_token_usage.py` | RFC 6750 — Bearer Token Usage | 11 | — |
| `test_rfc7636_proof_key_for_code_exchange.py` | RFC 7636 — Proof Key for Code Exchange | 17 | — |
| `test_rfc7009_token_revocation.py` | RFC 7009 — Token Revocation | 13 | — |
| `test_rfc7662_token_introspection.py` | RFC 7662 — Token Introspection | 15 | — |
| `test_rfc8414_authorization_server_metadata.py` | RFC 8414 — Authorization Server Metadata | 16 | — |
| `test_rfc8628_device_authorization_grant.py` | RFC 8628 — Device Authorization Grant | 22 | — |
| `test_rfc9068_access_token_profile.py` | RFC 9068 — JWT Profile for Access Tokens | 22 | — |
| `test_rfc9700_security_best_practice.py` | RFC 9700 — Security Best Current Practice | 17 | — |

A gap would be a requirement this server does not meet: its test is written as
the standard reads and marked `xfail(strict=True)`, so meeting the requirement
turns the mark into a failure and the mark is removed in the same change.
There are none left — every test here passes unmarked. The *deliberate
deviations* at the end of this file are a different thing: each meets its
requirement and differs only in how it names a refusal, or answers a case the
standard leaves to the server.

## RFC 6749 — The OAuth 2.0 Authorization Framework

| § | Requirement | Covered by |
|---|---|---|
| 2.3.1 | The authorization server MUST support HTTP Basic for client credentials | `test_a_client_may_authenticate_with_the_basic_scheme` |
| 2.3.1 | Credentials in the request body are accepted beside the header | `test_a_client_may_authenticate_in_the_request_body` |
| 3.1 | The authorization endpoint MUST support `GET` | `test_the_authorization_endpoint_answers_a_get` |
| 3.1 | The server MUST ignore unrecognized request parameters | `test_a_parameter_this_server_does_not_know_is_ignored` |
| 3.1 | A parameter sent without a value MUST be treated as omitted | `test_a_parameter_sent_without_a_value_counts_as_omitted` |
| 3.1.2.3 | The server MUST compare and match the redirect URI against the registered ones | `test_a_redirect_uri_the_client_never_registered_is_refused` |
| 3.1.2.4 | A refusal about the redirect URI MUST NOT redirect the browser to it | `test_a_refusal_about_the_redirect_uri_is_not_itself_a_redirect` |
| 3.2 | The token endpoint MUST ignore unrecognized request parameters | `test_the_token_endpoint_ignores_a_parameter_it_does_not_know` |
| 3.1, 3.2 | A parameter MUST NOT be included more than once | `test_a_parameter_the_request_repeats_is_refused`; the parameter that chooses the flow, judged before any grant is offered the request — `test_a_repeated_grant_type_is_refused_before_a_grant_is_chosen`, `test_a_repeated_response_type_is_refused_before_a_grant_is_chosen` |
| 3.3, 5.1 | A grant differing from the request MUST name the `scope` granted | `test_a_grant_that_differs_from_the_request_names_the_scope_it_gave` |
| 4.1.2 | The authorization response carries the `state` it was sent | `test_the_authorization_response_carries_the_state_it_was_sent` |
| 4.1.2 | A code used more than once MUST be denied | `test_a_code_used_a_second_time_is_denied` |
| 4.1.2.1, 5.2 | `error` and `error_description` MUST stay inside %x20-21 / %x23-5B / %x5D-7E | `test_the_words_a_refusal_uses_stay_inside_the_allowed_characters` |
| 4.1.3 | The server MUST require client authentication for a confidential client | `test_a_confidential_client_must_authenticate_to_redeem_a_code` |
| 4.1.3 | The server MUST ensure the code was issued to the authenticated client | `test_a_code_cannot_be_redeemed_by_another_client` |
| 4.1.3 | The `redirect_uri` values MUST be identical | `test_a_code_is_redeemed_only_against_the_redirect_uri_it_was_tied_to`, `test_a_code_is_refused_when_the_redirect_uri_is_left_out` |
| 4.3.2 | The server MUST validate the resource owner's credentials | `test_credentials_this_server_does_not_accept_are_refused` |
| 4.4.2 | The server MUST authenticate the client | `test_a_client_acting_for_itself_must_authenticate` |
| 5.1 | A response carrying a token MUST carry `Cache-Control: no-store` and `Pragma: no-cache` | `test_an_answer_carrying_a_token_may_not_be_cached` |
| 5.1 | The answer names the token, its type and its remaining lifetime | `test_the_token_answer_names_the_scheme_and_what_is_left_of_the_lifetime` |
| 5.2 | A client that tried the `Authorization` header MUST get `401` and a matching `WWW-Authenticate` | `test_a_client_that_tried_the_basic_scheme_is_told_which_scheme_to_try` |
| 5.2 | `unsupported_grant_type` for a grant this server does not run | `test_a_grant_type_this_server_does_not_run_is_named_as_unsupported` |
| 6 | The server MUST ensure the refresh token was issued to the authenticated client | `test_a_refresh_token_cannot_be_spent_by_another_client` |
| 6 | The requested scope MUST NOT include a scope never granted | `test_a_refresh_may_not_ask_for_a_scope_that_was_never_granted` |
| 6 | The server MUST validate the refresh token | `test_a_refresh_token_that_was_already_spent_is_invalid`, `test_a_refresh_token_this_server_cannot_read_is_invalid` |

## RFC 6750 — Bearer Token Usage

| § | Requirement | Covered by |
|---|---|---|
| 2.1 | A resource server MUST support the `Authorization: Bearer` method | `test_a_token_is_accepted_in_the_authorization_header` |
| 2.1 | The scheme name is case-insensitive (RFC 9110 § 11.1) | `test_the_scheme_is_read_whatever_case_it_was_written_in` |
| 3 | A request with no credentials MUST be answered with `WWW-Authenticate` | `test_a_request_carrying_no_token_is_answered_with_a_challenge` |
| 3 | A request whose token does not grant access MUST be answered with `WWW-Authenticate` | `test_a_token_this_server_cannot_read_is_answered_with_a_challenge` |
| 3 | Every challenge MUST use the `Bearer` scheme | `test_every_challenge_names_the_bearer_scheme` |
| 3 | The scheme MUST be followed by one or more auth-param values | `test_the_challenge_for_an_unread_token_carries_an_attribute`, `test_the_challenge_for_too_little_privilege_carries_attributes` |
| 3 | `realm`, `scope`, `error`, `error_description`, `error_uri` MUST NOT appear more than once | `test_no_attribute_of_a_challenge_is_written_twice` |
| 3 | The character sets of the `scope`, `error` and `error_description` values | `test_the_words_a_challenge_uses_stay_inside_the_allowed_characters` |
| 3.1 | `insufficient_scope`, answered `403`, naming the scope needed | `test_a_token_lacking_the_privilege_asked_for_says_so` |
| 3.1 | A request lacking any authentication information SHOULD NOT be told a reason | `test_a_request_that_presented_nothing_is_told_no_reason` |

The `invalid_token` code of § 3.1 is recorded under RFC 9068 § 4 below, which
is where it is a MUST.

## RFC 7636 — Proof Key for Code Exchange

| § | Requirement | Covered by |
|---|---|---|
| Appendix B | The standard's own vector: verifier `dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk` → challenge `E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM` | `test_the_standards_own_example_verifier_is_the_encoded_octets`, `test_the_standards_own_example_digest_is_the_hash_of_that_verifier`, `test_the_standards_own_example_challenge_verifies`, `test_another_verifier_does_not_satisfy_that_challenge` |
| 4.2 | `S256` is `BASE64URL-ENCODE(SHA256(ASCII(code_verifier)))` | `test_the_hashed_method_is_the_digest_encoded_without_padding` |
| 4.2 | `plain` is the verifier itself | `test_the_unhashed_method_compares_the_two_values_directly` |
| 4.2 | `S256` is mandatory to implement on the server | `test_the_hashed_method_is_the_one_this_server_names_mandatory` |
| 4.3 | `code-challenge = 43*128unreserved` | `test_a_challenge_the_standard_would_not_accept_is_refused` |
| 4.3 | `code_challenge_method` defaults to `plain` | `test_the_method_defaults_to_the_unhashed_one_when_the_request_names_none` |
| 4.4 | The server MUST associate the challenge and method with the code | implied by every redemption test; the association is read back at the token endpoint |
| 4.4 | The server MUST NOT hand the challenge back in an extractable form | `test_the_code_a_client_is_handed_does_not_carry_the_challenge_in_the_clear` |
| 4.4.1 | A public client sending no challenge MUST be answered `invalid_request` | `test_a_public_client_sending_no_challenge_is_told_the_request_is_bad` |
| 4.4.1 | An unsupported transformation MUST be answered `invalid_request` | `test_a_transformation_this_server_does_not_run_is_told_the_request_is_bad` |
| 4.5 | `code_verifier` is required when the code carries a challenge | `test_a_code_tied_to_a_challenge_is_not_redeemed_without_a_verifier` |
| 4.6 | Equal values MUST continue processing | `test_the_right_verifier_redeems_the_code` |
| 4.6 | Unequal values MUST be answered `invalid_grant` | `test_a_verifier_that_does_not_derive_the_challenge_is_an_invalid_grant` |
| 4.1 | `code-verifier = 43*128unreserved` | `test_a_verifier_the_standard_would_not_accept_never_reaches_the_comparison` |
| 7.2 | A server supporting `S256` SHOULD NOT accept `plain` | `test_a_client_not_registered_for_the_unhashed_method_is_refused` — only a client whose registration says so may use it |

## RFC 7009 — Token Revocation

| § | Requirement | Covered by |
|---|---|---|
| 1 | Revoking a refresh token MUST be supported | `test_a_refresh_token_can_be_withdrawn` |
| 1 | Revoking an access token SHOULD be supported | `test_an_access_token_can_be_withdrawn` |
| 2.1 | `token` is required | `test_a_request_naming_no_token_is_refused` |
| 2.1 | A hint that does not locate the token MUST NOT stop the search | `test_a_hint_naming_the_wrong_kind_still_finds_the_token`, `test_a_refresh_token_offered_under_the_access_token_hint_is_still_found` |
| 2.1 | Revoking a refresh token SHOULD invalidate the access tokens of the same grant | `test_withdrawing_a_refresh_token_also_withdraws_its_access_token` |
| 2.1 | The client credentials are validated first | `test_a_client_must_authenticate_to_withdraw_a_token` |
| 2.1 | The invalidation takes place immediately | `test_the_withdrawal_takes_effect_at_once` |
| 2.2 | `200` when revoked, and `200` for an invalid token | `test_a_token_this_server_never_issued_is_answered_as_done`, `test_withdrawing_the_same_token_twice_is_answered_as_done_both_times` |
| 2.2 | An invalid hint value is ignored | `test_a_hint_value_this_server_does_not_know_is_ignored` |
| 2.2.1 | The error presentation follows RFC 6749 § 5.2 | `test_a_client_must_authenticate_to_withdraw_a_token` |
| — | The answer may not be cached | `test_the_answer_to_a_withdrawal_may_not_be_cached` |

## RFC 7662 — Token Introspection

| § | Requirement | Covered by |
|---|---|---|
| 2.1 | `token` is required | `test_a_request_naming_no_token_is_refused` |
| 2.1 | The endpoint MUST require authorization | `test_nobody_may_ask_without_authorization` |
| 2.1 | A hint that does not locate the token MUST NOT stop the search | `test_a_hint_naming_the_wrong_kind_still_finds_the_token`, `test_a_refresh_token_is_read_as_well_as_an_access_token` |
| 2.2 | `active` is required, beside the fields of the section | `test_a_live_token_is_reported_active_with_what_it_carries` |
| 2.2 | The answer is a JSON object | `test_the_answer_is_a_json_document` |
| 2.2 | An inactive, unknown or unreadable token MUST be answered `active: false` | `test_a_token_this_server_cannot_read_is_reported_inactive`, `test_a_withdrawn_token_is_reported_inactive`, `test_a_refresh_token_sealed_for_another_client_is_reported_inactive` |
| 2.2 | An inactive token SHOULD NOT be described further | `test_an_inactive_token_is_described_no_further` |
| 2.2 | The server decides `active`, not the request | `test_a_client_cannot_make_a_token_look_active_by_asking_about_it` |
| 2.3 | Invalid client credentials MUST be answered `401` | `test_a_client_whose_credentials_are_wrong_is_told_so` |
| 2.3 | A query about an inactive token is not an error | `test_asking_about_an_inactive_token_is_not_an_error` |
| 4 | The answer MUST NOT be cached beyond what it says | `test_the_answer_may_not_be_cached_indefinitely` |

## RFC 8414 — Authorization Server Metadata

| § | Requirement | Covered by |
|---|---|---|
| 2 | `issuer` is required | `test_the_description_names_the_issuer` |
| 2 | The issuer has no query or fragment | `test_the_issuer_carries_no_query_and_no_fragment` |
| 2 | `authorization_endpoint`, `token_endpoint` | `test_the_description_names_the_authorization_and_token_endpoints` |
| 2 | Every endpoint named is a URL | `test_every_endpoint_named_is_an_absolute_url_under_the_issuer` |
| 2 | `jwks_uri` MUST use the `https` scheme | `test_the_key_set_is_published_over_https` |
| 2 | `response_types_supported` is required | `test_the_description_names_the_responses_this_server_issues` |
| 2 | `grant_types_supported` | `test_the_description_names_the_flows_this_server_runs` |
| 2 | `token_endpoint_auth_methods_supported` | `test_the_description_names_how_a_client_may_authenticate` |
| 2 | `scopes_supported` | `test_the_description_names_the_scopes_a_client_may_ask_for` |
| 2 | `code_challenge_methods_supported` | `test_the_description_names_how_a_proof_key_may_be_derived` |
| 3 | The document MUST be available at `/.well-known/oauth-authorization-server` | `test_the_description_lives_at_the_well_known_path` |
| 3.1 | The document MUST be queried with `GET` | `test_the_description_is_read_with_a_get` |
| 3.2 | A successful answer MUST be `200 OK` and `application/json` | `test_a_successful_answer_is_two_hundred_and_json` |
| 3.2 | Claims with zero elements MUST be omitted | `test_a_field_with_nothing_in_it_is_left_out` |
| 3.3 | The `issuer` returned MUST be identical to the one the document was read under | `test_the_issuer_published_is_the_one_the_document_was_read_under` |
| 2 | The `jwks_uri` answers | `test_the_key_set_is_served_where_the_description_says` |

`signed_metadata` (§ 2.1) is not published; the section makes it optional.

## RFC 8628 — Device Authorization Grant

| § | Requirement | Covered by |
|---|---|---|
| 3.1 | A public client identifies itself with `client_id` | `test_a_device_names_itself_and_needs_nothing_else`, `test_a_request_naming_no_client_is_refused` |
| 3.1 | A parameter sent without a value MUST be treated as omitted | `test_a_parameter_sent_without_a_value_counts_as_omitted` |
| 3.1 | The server MUST ignore unrecognized request parameters | `test_a_parameter_this_server_does_not_know_is_ignored` |
| 3.1 | The `scope` of RFC 6749 § 3.3 travels with the request | `test_a_scope_the_client_is_not_registered_for_is_refused` |
| 3.2 | `device_code`, `user_code`, `verification_uri`, `expires_in` are required | `test_the_answer_carries_everything_the_standard_requires` |
| 3.2 | `200 (OK)` and `application/json` | `test_the_answer_is_two_hundred_and_json_and_uncached` |
| 3.2 | `verification_uri_complete` includes the user code | `test_the_answer_may_carry_a_uri_with_the_code_already_in_it` |
| 3.2 | `interval` | `test_the_answer_says_how_long_a_device_should_wait_between_polls` |
| 3.3 | A user-interaction sequence starting at `verification_uri` MUST be implemented | `test_the_person_is_sent_somewhere_to_type_the_code` — partly: the address and the code are this server's, the page is the application's |
| 3.4 | `grant_type` MUST be `urn:ietf:params:oauth:grant-type:device_code` | `test_the_flow_is_asked_for_by_the_name_the_standard_registers`, `test_a_poll_naming_another_grant_type_earns_nothing` |
| 3.4 | `device_code` is required | `test_a_poll_naming_no_device_code_is_refused` |
| 3.5 | `authorization_pending` | `test_a_device_nobody_has_approved_yet_is_told_to_keep_waiting` |
| 3.5 | `slow_down` | `test_a_device_polling_too_fast_is_told_to_slow_down` |
| 3.5 | `access_denied` | `test_a_device_the_owner_refused_is_told_so` |
| 3.5 | An approved grant is answered as RFC 6749 § 5.1 | `test_an_approved_device_is_issued_a_token` |
| 3.5 | A code already exchanged, or never issued, earns nothing | `test_a_device_code_already_exchanged_cannot_be_exchanged_again`, `test_a_device_code_this_server_never_issued_is_refused` |
| 6.1 | The user code's alphabet and entropy | `test_the_user_code_alphabet_is_the_one_the_standard_suggests`, `test_the_user_code_carries_more_entropy_than_the_standard_asks_for`, `test_a_user_code_is_only_ever_issued_once` |

`expired_token` (§ 3.5) is raised by the grant and is covered by its unit test
(`tests/unit/grant/test_device_code_grant.py` in `xtr-security-oauth2-server-core`): nothing in the protocol expires
a code on request, and a served test cannot wait out the lifetime.

Rate-limiting the verification page (§ 5.1, § 6.1) is the application's, since
the page is: documented in the package README rather than tested here.

## RFC 9068 — JWT Profile for Access Tokens

| § | Requirement | Covered by |
|---|---|---|
| 2.1 | A token MUST be signed | `test_a_token_is_signed` |
| 2.1 | A token MUST NOT use `none`, and `RS256` MUST be among the algorithms | `test_a_token_names_a_real_signing_algorithm` |
| 2.1 | `typ` MUST declare the profile's media type | `test_a_token_declares_the_media_type_of_the_profile` |
| 2.2 | `iss`, `exp`, `aud`, `sub`, `client_id`, `iat`, `jti` are required | `test_a_token_carries_every_claim_the_profile_requires`, `test_a_tokens_window_is_a_pair_of_whole_seconds` |
| 2.2 | `sub` for a client-credentials token names the client | `test_a_token_a_client_was_issued_for_itself_names_the_client_as_subject` |
| 2.2.3 | `scope`, as space-delimited names | `test_a_token_names_what_it_may_do_as_space_delimited_text` |
| 2.2.2 | Extra claims may not redefine the profile's own | `test_the_claims_the_profile_defines_cannot_be_written_over` |
| 4 | The reader MUST verify `typ` is `at+jwt` or `application/at+jwt` | `test_a_token_declaring_another_media_type_is_refused`, `test_a_token_declaring_the_full_media_type_is_accepted` |
| 4 | `iss` MUST match exactly | `test_a_token_naming_another_issuer_is_refused` |
| 4 | `aud` MUST contain an identifier the reader expects, and the token MUST be rejected otherwise | `test_a_token_addressed_to_the_resource_that_reads_it_is_accepted`, `test_a_token_addressed_elsewhere_is_refused`; **deviation** when no audience is configured — `test_a_deployment_naming_no_audience_does_not_check_one` |
| 4 | The signature MUST be validated, and `alg: none` MUST be rejected | `test_a_token_signed_with_no_algorithm_at_all_is_refused`, `test_a_token_no_trusted_key_signed_is_refused` |
| 4 | The current time MUST be before `exp` | `test_a_token_whose_window_has_closed_is_refused` |
| 4 | A failed check MUST include the error code `invalid_token` | `test_a_refusal_names_the_error_code_the_profile_requires`; the check itself is pinned by `test_a_refused_token_opens_nothing` |
| 5, 6 | A token is distinguishable, and a refusal names none | `test_two_tokens_never_share_an_identifier`, `test_the_words_a_refusal_carries_never_name_the_token` |
| 4 | `kid` lets the reader find the key | `test_a_token_names_the_key_it_was_signed_with` |

## RFC 9700 — Security Best Current Practice

Only the requirements addressed to an authorization server are covered; the
ones addressed to clients are a client's to meet.

| § | Requirement | Covered by |
|---|---|---|
| 2.1, 4.1.3 | Redirect URIs MUST be matched by exact string comparison | `test_a_redirect_uri_is_matched_as_the_very_same_text` |
| 4.1.3 | A loopback redirect MUST be allowed a variable port (RFC 8252 § 7.3) | `test_a_loopback_redirect_may_arrive_on_another_port`, `test_the_exception_is_about_the_port_and_nothing_else`, `test_a_redirect_naming_the_loopback_by_name_is_not_the_exception` |
| 2.1, 4.11 | The server MUST NOT forward the browser to a URI a query parameter chose | `test_a_refusal_never_forwards_the_browser_somewhere_the_request_chose`, `test_a_refusal_the_client_is_entitled_to_goes_only_to_a_registered_uri` |
| 2.1.1 | The server MUST support PKCE | `test_this_server_supports_the_proof_key_mechanism` |
| 2.1.1 | The server MUST provide a way to detect that support | `test_the_support_can_be_detected_from_the_published_description` |
| 2.1.1 | A challenge that was sent MUST be enforced at the token endpoint | `test_a_challenge_that_was_sent_is_enforced_at_the_token_endpoint` |
| 2.1.1 | A public client MUST use PKCE | `test_a_public_client_is_made_to_commit_to_a_proof_key` |
| 2.1.1, 4.8.2 | A `code_verifier` arriving for a code tied to no challenge MUST be rejected | `test_a_verifier_arriving_for_a_code_tied_to_no_challenge_is_refused` |
| 4.5 | Code injection and misuse | `test_a_code_is_good_for_exactly_one_exchange`, `test_a_stolen_code_is_worth_nothing_without_the_proof_key` |
| 2.2.2, 4.14.2 | Refresh token rotation, the previous token invalidated | `test_a_refresh_hands_back_a_new_refresh_token`, `test_the_refresh_token_that_was_spent_stops_working` |
| 4.14.2 | A refresh token MUST stay bound to the scope consented to | `test_a_refresh_token_stays_bound_to_what_was_consented_to` |
| 2.5 | The server SHOULD enforce client authentication | `test_a_client_holding_a_secret_is_made_to_present_it` |

### Not covered, by decision

- **Mix-up defence (§ 2.1, § 4.4).** The countermeasure is the `iss`
  authorization-response parameter of RFC 9207, which this server does not
  issue. RFC 9207 is out of scope by the plan (§ 5), so the requirement is not
  met and there is no test of it. A client that talks to more than one
  authorization server has to use distinct redirect URIs instead (§ 4.4.2.2).
- **Sender-constrained access tokens (§ 2.2.1, SHOULD).** Mutual TLS (RFC 8705)
  and DPoP (RFC 9449) are out of scope by the plan (§ 5).
- **The resource owner password grant (§ 2.4, "MUST NOT be used").** The flow
  ships, off by default, for parity with the library this package was
  translated from; a deployment that turns it on is choosing against this
  section. Several tests here use it, because it is the cheapest way to
  establish a resource owner without a browser.
- **The implicit grant (§ 2.1.2, SHOULD NOT be used).** Ships, off by default,
  for the same reason.
- **Transport security.** Every standard here requires TLS on every endpoint
  (RFC 6749 § 1.6, RFC 6750 § 5.1, RFC 7009 § 2, RFC 7662 § 2.1, RFC 8414 § 5,
  RFC 8628 § 3.1, RFC 9068 § 4). It is the deployment's, not this server's: no
  test can assert it of an application served over ASGI.
- **Client-side requirements.** CSRF protection on the redirection endpoint
  (RFC 6749 § 10.12, RFC 9700 § 2.1), discarding the resource owner's password
  (§ 4.3.2), ignoring unrecognized response parameters (§ 4.1.2) — all a
  client's.
- **Brute-force protection on the token and verification endpoints**
  (RFC 6749 § 4.3.2, RFC 8628 § 5.1). The application's: the package README
  documents it with a rate-limiter example.

## Deliberate deviations

Each of these meets the requirement and differs in how it names the refusal, or
answers a case the standard leaves to the server. None is a gap; each is pinned
by the test named. A deviation the plan settled says which section of it; the
rest are the naming of the library this package was translated from, recorded
here and nowhere else.

| Where | This server | The standard's catalogue | Why |
|---|---|---|---|
| A code redeemed against another redirect URI | `invalid_request` | RFC 6749 § 5.2 puts it under `invalid_grant` | Library (up) naming, recorded here; `test_a_code_is_redeemed_only_against_the_redirect_uri_it_was_tied_to` |
| A code redeemed by another client | `invalid_request` | the same | Library (up) naming, recorded here; `test_a_code_cannot_be_redeemed_by_another_client` |
| A confidential client that sent no secret | `invalid_request` / `400` | RFC 6749 § 5.2 puts "no client authentication included" under `invalid_client` | A missing parameter is named rather than counted as a failed authentication — library (up) naming, recorded here; `test_a_confidential_client_must_authenticate_to_redeem_a_code` |
| The challenge refusing a token that was presented | `Bearer error="invalid_token", error_description="…"`, no `realm` | RFC 6750 § 3 has `realm` as a SHOULD | The refusal is built out of the error, which knows which check failed and not which firewall was asked; the challenge that starts authentication names the realm. Recorded here; `test_the_challenge_for_an_unread_token_carries_an_attribute` |
| A refresh token that is invalid, expired or revoked | `invalid_grant` / `400` | RFC 6749 § 5.2, which the library answers as `invalid_request` / `401` | Ours follows the text (plan § 6b); `test_a_refresh_token_that_was_already_spent_is_invalid` |
| Revoking a token issued to another client | `200`, nothing withdrawn | RFC 7009 § 2.1 has the request refused | A refusal would confirm to the asking client that the token exists (plan, Phase 5); `test_a_token_belonging_to_another_client_is_answered_as_done` |
| Introspecting an access token issued to another client | `active: true`, naming the client it belongs to | RFC 7662 § 2.2 allows `active: false` for "a token the protected resource is not allowed to know about" | An access token is a signed document any resource server reads on its own, so it is read for what it says (plan § 4b); `test_an_access_token_issued_to_another_client_is_still_read` |
| An access token with no configured audience | `aud` is the client id, and is not checked | RFC 9068 § 4 requires the check | Recorded in the plan, Phase 5; `test_a_deployment_naming_no_audience_does_not_check_one` |
