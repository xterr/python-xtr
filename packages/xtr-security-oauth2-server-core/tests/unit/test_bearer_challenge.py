"""Writing the ``WWW-Authenticate`` challenge a caller that proved nothing is owed."""

from __future__ import annotations

from xtr_security_oauth2_server_core.bearer_challenge import bearer_challenge


def test_one_auth_param_follows_the_scheme() -> None:
    # "All challenges defined by this specification MUST use the auth-scheme
    # value "Bearer". This scheme MUST be followed by one or more auth-param
    # values" (RFC 6750 section 3).
    assert bearer_challenge("realm", "api") == 'Bearer realm="api"'


def test_further_auth_params_follow_in_the_order_they_were_named() -> None:
    written = bearer_challenge(
        "error",
        "invalid_token",
        error_description="The access token could not be accepted.",
    )

    assert written == (
        'Bearer error="invalid_token", error_description="The access token could not be accepted."'
    )


def test_a_character_the_standard_does_not_allow_is_dropped() -> None:
    # "Values for the "error" and "error_description" attributes ... MUST NOT
    # include characters outside the set %x20-21 / %x23-5B / %x5D-7E"
    # (RFC 6750 section 3) — which rules out the double quote and the
    # backslash that would otherwise have to be escaped, and the control
    # characters that would split the header.
    written = bearer_challenge("realm", 'a realm\r\nwith "quotes" and a \\ in it\x7f')

    assert written == 'Bearer realm="a realmwith quotes and a  in it"'
