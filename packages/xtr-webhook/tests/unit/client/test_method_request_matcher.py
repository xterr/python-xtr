from __future__ import annotations

from xtr_http_message import ServerRequest

from xtr_webhook.client import MethodRequestMatcher


def test_it_claims_a_request_whose_method_it_was_given() -> None:
    assert MethodRequestMatcher("POST").matches(ServerRequest("POST", "/webhook")) is True


def test_it_refuses_a_request_whose_method_it_was_not_given() -> None:
    assert MethodRequestMatcher("POST", "PUT").matches(ServerRequest("GET", "/webhook")) is False


def test_it_ignores_the_case_of_the_methods_it_was_given() -> None:
    assert MethodRequestMatcher("post").matches(ServerRequest("POST", "/webhook")) is True


def test_it_ignores_the_case_of_the_method_that_arrived() -> None:
    assert MethodRequestMatcher("POST").matches(ServerRequest("post", "/webhook")) is True


def test_it_claims_a_request_matching_any_one_of_several_methods() -> None:
    matcher = MethodRequestMatcher("POST", "PUT")

    assert matcher.matches(ServerRequest("PUT", "/webhook")) is True


def test_it_claims_nothing_when_it_was_given_no_method() -> None:
    assert MethodRequestMatcher().matches(ServerRequest("POST", "/webhook")) is False
