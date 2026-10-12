"""``OAuthServerError`` is the protocol answer: a named error, its status and its payload."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import parse_qs, urlsplit

import pytest
from xtr_http_message import Response

from tests.support.messages import body_of, document_of, server_request
from xtr_security_oauth2_server.exception import OAuth2Error, OAuthServerError

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

_MALFORMED_REQUEST = (
    "The request is missing a required parameter, includes an invalid parameter value, "
    "includes a parameter more than once, or is otherwise malformed."
)
_BAD_GRANT = (
    "The provided authorization grant (e.g., authorization code, resource owner credentials) "
    "or refresh token is invalid, expired, revoked, does not match the redirection URI used in "
    "the authorization request, or was issued to another client."
)
_STILL_PENDING = (
    "The authorization request is still pending as the end user hasn't yet completed the user "
    "interaction steps. The client SHOULD repeat the Access Token Request to the token endpoint"
)
_POLL_SLOWER = (
    "The authorization request is still pending and polling should continue, but the interval "
    "MUST be increased by 5 seconds for this and all subsequent requests."
)
_UNEXPECTED_CONDITION = (
    "The authorization server encountered an unexpected condition which prevented it from "
    "fulfilling the request: the signing key is unreadable"
)


class _Answer(NamedTuple):
    """One row of the error catalogue, written out independently of the library."""

    error_type: str
    code: int
    status: int
    message: str
    hint: str | None


def _token_request(authorization: str | None = None) -> ServerRequestInterface:
    headers = {} if authorization is None else {"Authorization": authorization}
    return server_request("POST", "https://server.test/token", headers=headers)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            OAuthServerError.unsupported_grant_type(),
            _Answer(
                "unsupported_grant_type",
                2,
                400,
                "The authorization grant type is not supported by the authorization server.",
                "Check that all required parameters have been provided",
            ),
        ),
        (
            OAuthServerError.invalid_request("grant_type"),
            _Answer(
                "invalid_request", 3, 400, _MALFORMED_REQUEST, "Check the `grant_type` parameter"
            ),
        ),
        (
            OAuthServerError.invalid_client(_token_request()),
            _Answer("invalid_client", 4, 401, "Client authentication failed", None),
        ),
        (
            OAuthServerError.invalid_scope("read"),
            _Answer(
                "invalid_scope",
                5,
                400,
                "The requested scope is invalid, unknown, or malformed",
                "Check the `read` scope",
            ),
        ),
        (
            OAuthServerError.invalid_credentials(),
            _Answer("invalid_grant", 6, 400, "The user credentials were incorrect.", None),
        ),
        (
            OAuthServerError.server_error("the signing key is unreadable"),
            _Answer("server_error", 7, 500, _UNEXPECTED_CONDITION, None),
        ),
        (
            OAuthServerError.invalid_refresh_token(),
            _Answer("invalid_grant", 8, 400, "The refresh token is invalid.", None),
        ),
        (
            OAuthServerError.access_denied(),
            _Answer(
                "access_denied",
                9,
                401,
                "The resource owner or authorization server denied the request.",
                None,
            ),
        ),
        (OAuthServerError.invalid_grant(), _Answer("invalid_grant", 10, 400, _BAD_GRANT, "")),
        (
            OAuthServerError.expired_token(),
            _Answer(
                "expired_token",
                11,
                400,
                "The `device_code` has expired and the device authorization session has concluded.",
                None,
            ),
        ),
        (
            OAuthServerError.authorization_pending(),
            _Answer("authorization_pending", 12, 400, _STILL_PENDING, ""),
        ),
        (OAuthServerError.slow_down(), _Answer("slow_down", 13, 400, _POLL_SLOWER, "")),
        (
            OAuthServerError.unauthorized_client(),
            _Answer(
                "unauthorized_client",
                14,
                400,
                "The authenticated client is not authorized to use this authorization grant type.",
                None,
            ),
        ),
        (
            OAuthServerError.unsupported_token_type(),
            _Answer(
                "unsupported_token_type",
                15,
                400,
                "The authorization server does not support the revocation of the presented "
                "token type.",
                None,
            ),
        ),
    ],
)
def test_every_named_error_carries_the_answer_the_protocol_names(
    error: OAuthServerError,
    expected: _Answer,
) -> None:
    assert error.get_error_type() == expected.error_type
    assert error.get_code() == expected.code
    assert error.get_http_status_code() == expected.status
    assert str(error) == expected.message
    assert error.get_hint() == expected.hint


def test_invalid_request_keeps_the_hint_it_was_given() -> None:
    error = OAuthServerError.invalid_request("code_challenge", "Use S256, not plain")

    assert error.get_hint() == "Use S256, not plain"


def test_invalid_scope_asks_for_a_scope_when_the_request_named_none() -> None:
    error = OAuthServerError.invalid_scope("")

    assert error.get_hint() == "Specify a scope in the request or set a default scope"


def test_invalid_scope_escapes_the_scope_it_repeats_back() -> None:
    # The scope comes straight from the request, and the hint may end up in a
    # page an application renders.
    error = OAuthServerError.invalid_scope("<script>alert('x')</script>")

    hint = error.get_hint()

    assert hint is not None
    assert "<script>" not in hint
    assert "&lt;script&gt;" in hint


def test_an_error_carries_no_redirect_unless_it_was_given_one() -> None:
    assert not OAuthServerError.invalid_scope("read").has_redirect()
    assert OAuthServerError.invalid_scope("read").get_redirect_uri() is None


def test_invalid_scope_carries_the_redirect_it_was_given() -> None:
    error = OAuthServerError.invalid_scope("read", "https://app.test/cb")

    assert error.has_redirect()
    assert error.get_redirect_uri() == "https://app.test/cb"


def test_access_denied_carries_the_redirect_it_was_given() -> None:
    error = OAuthServerError.access_denied("the user said no", "https://app.test/cb")

    assert error.has_redirect()
    assert error.get_redirect_uri() == "https://app.test/cb"


def test_the_payload_restates_the_error_and_its_description() -> None:
    error = OAuthServerError.invalid_credentials()

    assert dict(error.get_payload()) == {
        "error": "invalid_grant",
        "error_description": "The user credentials were incorrect.",
    }


def test_the_payload_carries_the_hint_when_there_is_one() -> None:
    error = OAuthServerError.invalid_request("grant_type")

    assert error.get_payload()["hint"] == "Check the `grant_type` parameter"


def test_set_payload_replaces_what_the_answer_carries() -> None:
    error = OAuthServerError.invalid_grant()

    error.set_payload({"error": "invalid_grant", "error_description": "say less"})

    assert dict(error.get_payload()) == {
        "error": "invalid_grant",
        "error_description": "say less",
    }


def test_the_answer_is_json_carrying_the_payload() -> None:
    error = OAuthServerError.unsupported_grant_type()

    answer = error.generate_http_response(Response())

    assert document_of(answer) == {
        "error": "unsupported_grant_type",
        "error_description": (
            "The authorization grant type is not supported by the authorization server."
        ),
        "hint": "Check that all required parameters have been provided",
    }


def test_the_answer_carries_the_status_and_the_content_type() -> None:
    error = OAuthServerError.invalid_credentials()

    answer = error.generate_http_response(Response())

    assert answer.get_status_code() == 400
    assert answer.get_header_line("content-type") == "application/json"


def test_the_payload_is_written_into_the_body_as_bytes() -> None:
    error = OAuthServerError.invalid_credentials()

    answer = error.generate_http_response(Response())

    written = bytes(answer.get_body())

    assert isinstance(written, bytes)
    assert b'"invalid_grant"' in written


def test_the_answer_overrides_the_payload_set_on_the_error() -> None:
    error = OAuthServerError.invalid_grant()
    error.set_payload({"error": "invalid_grant"})

    answer = error.generate_http_response(Response())

    assert document_of(answer) == {"error": "invalid_grant"}


def test_a_redirecting_error_answers_a_302_with_the_payload_in_the_query() -> None:
    error = OAuthServerError.invalid_scope("read", "https://app.test/cb")

    answer = error.generate_http_response(Response())

    location = answer.get_header_line("location")
    assert answer.get_status_code() == 302
    assert location.startswith("https://app.test/cb?")
    assert parse_qs(urlsplit(location).query) == {
        "error": ["invalid_scope"],
        "error_description": ["The requested scope is invalid, unknown, or malformed"],
        "hint": ["Check the `read` scope"],
    }


def test_the_query_joins_on_with_an_ampersand_when_the_redirect_already_has_one() -> None:
    error = OAuthServerError.access_denied(None, "https://app.test/cb?state=xyz")

    answer = error.generate_http_response(Response())

    location = answer.get_header_line("location")
    assert location.startswith("https://app.test/cb?state=xyz&")
    assert parse_qs(urlsplit(location).query)["state"] == ["xyz"]
    assert parse_qs(urlsplit(location).query)["error"] == ["access_denied"]


def test_a_redirecting_error_can_answer_with_the_payload_in_the_fragment() -> None:
    error = OAuthServerError.access_denied(None, "https://app.test/cb")

    answer = error.generate_http_response(Response(), use_fragment=True)

    location = answer.get_header_line("location")
    assert location.startswith("https://app.test/cb#")
    assert parse_qs(urlsplit(location).fragment)["error"] == ["access_denied"]


def test_the_fragment_joins_on_with_an_ampersand_when_the_redirect_already_has_one() -> None:
    error = OAuthServerError.access_denied(None, "https://app.test/cb#state=xyz")

    answer = error.generate_http_response(Response(), use_fragment=True)

    location = answer.get_header_line("location")
    assert location.startswith("https://app.test/cb#state=xyz&")
    assert parse_qs(urlsplit(location).fragment)["state"] == ["xyz"]


def test_a_redirecting_answer_carries_nothing_but_the_location() -> None:
    # The browser follows the redirect; a JSON content type on a 302 would only
    # describe a body that is not there.
    error = OAuthServerError.access_denied(None, "https://app.test/cb")

    answer = error.generate_http_response(Response())

    assert tuple(answer.get_headers()) == ("Location",)
    assert body_of(answer) == ""


def test_asking_for_the_answer_twice_yields_the_same_redirect() -> None:
    error = OAuthServerError.access_denied(None, "https://app.test/cb")

    first = error.generate_http_response(Response())
    second = error.generate_http_response(Response())

    assert first.get_header_line("location") == second.get_header_line("location")
    assert error.get_redirect_uri() == "https://app.test/cb"


def test_invalid_client_asks_again_for_the_basic_credentials_that_were_sent() -> None:
    error = OAuthServerError.invalid_client(_token_request("Basic YXBwOnMzY3IzdA=="))

    assert error.get_http_headers()["www-authenticate"] == 'Basic realm="OAuth"'


def test_invalid_client_asks_again_for_the_bearer_token_that_was_sent() -> None:
    error = OAuthServerError.invalid_client(_token_request("Bearer ey.Jh.bGc"))

    assert error.get_http_headers()["www-authenticate"] == 'Bearer realm="OAuth"'


def test_invalid_client_asks_for_no_scheme_when_the_request_tried_none() -> None:
    # The client put its credentials in the form instead, so there is no scheme
    # to name back at it.
    error = OAuthServerError.invalid_client(_token_request())

    assert "www-authenticate" not in error.get_http_headers()


def test_invalid_client_reads_an_empty_authorization_header_as_no_attempt() -> None:
    # Some servers hand on an empty header line when the client sent none.
    error = OAuthServerError.invalid_client(_token_request(""))

    assert "www-authenticate" not in error.get_http_headers()


def test_the_answer_to_invalid_client_carries_the_scheme_it_asks_for() -> None:
    error = OAuthServerError.invalid_client(_token_request("Basic YXBwOnMzY3IzdA=="))

    answer = error.generate_http_response(Response())

    assert answer.get_status_code() == 401
    assert answer.get_header_line("www-authenticate") == 'Basic realm="OAuth"'


def test_no_other_error_ever_asks_for_credentials() -> None:
    error = OAuthServerError.unauthorized_client()

    assert dict(error.get_http_headers()) == {"content-type": "application/json"}


def test_it_is_one_of_the_librarys_errors() -> None:
    assert issubclass(OAuthServerError, OAuth2Error)


def test_it_keeps_the_error_it_was_raised_from() -> None:
    cause = ValueError("the payload could not be decrypted")

    with pytest.raises(OAuthServerError) as raised:
        raise OAuthServerError.invalid_refresh_token("Cannot decrypt the refresh token") from cause

    assert raised.value.__cause__ is cause


def test_its_repr_shows_no_credential_the_request_carried() -> None:
    error = OAuthServerError.invalid_client(_token_request("Basic YXBwOnMzY3IzdA=="))

    assert "YXBwOnMzY3IzdA==" not in repr(error)
