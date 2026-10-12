from __future__ import annotations

from xtr_http_message import ServerRequest

from xtr_webhook.client import ChainRequestMatcher, IsJsonRequestMatcher, MethodRequestMatcher

_JSON_POST = ServerRequest("POST", "/webhook", {"Content-Type": "application/json"})


def test_it_claims_a_request_every_link_claims() -> None:
    matcher = ChainRequestMatcher([MethodRequestMatcher("POST"), IsJsonRequestMatcher()])

    assert matcher.matches(_JSON_POST) is True


def test_it_refuses_a_request_one_link_refuses() -> None:
    matcher = ChainRequestMatcher([MethodRequestMatcher("GET"), IsJsonRequestMatcher()])

    assert matcher.matches(_JSON_POST) is False


def test_a_chain_of_nothing_claims_every_request() -> None:
    assert ChainRequestMatcher([]).matches(ServerRequest("GET", "/anything")) is True


def test_it_keeps_the_links_it_was_given_as_they_were() -> None:
    links = [MethodRequestMatcher("GET")]
    matcher = ChainRequestMatcher(links)
    links.clear()

    assert matcher.matches(_JSON_POST) is False
