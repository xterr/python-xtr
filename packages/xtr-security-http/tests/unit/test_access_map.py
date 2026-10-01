"""The access map finds the attribute of the first rule a request matches."""

from __future__ import annotations

from tests.support.requests import make_request
from xtr_security_http.access_map import AccessMap
from xtr_security_http.access_map_interface import AccessMapInterface
from xtr_security_http.request_matcher.path_request_matcher import PathRequestMatcher


def _map() -> AccessMap:
    access_map = AccessMap()
    access_map.add(PathRequestMatcher(r"^/api/admin"), "ROLE_ADMIN")
    access_map.add(PathRequestMatcher(r"^/api"), "IS_AUTHENTICATED")
    return access_map


def test_the_first_matching_rule_decides() -> None:
    request = make_request()
    request.scope["path"] = "/api/admin/panel"

    assert _map().get_attribute(request) == "ROLE_ADMIN"


def test_a_broader_rule_matches_when_the_narrow_one_does_not() -> None:
    request = make_request()
    request.scope["path"] = "/api/books"

    assert _map().get_attribute(request) == "IS_AUTHENTICATED"


def test_no_rule_matches_returns_none() -> None:
    request = make_request()
    request.scope["path"] = "/public"

    assert _map().get_attribute(request) is None


def test_an_empty_map_matches_nothing() -> None:
    request = make_request()
    request.scope["path"] = "/api"

    assert AccessMap().get_attribute(request) is None


def test_the_map_satisfies_its_interface() -> None:
    assert isinstance(_map(), AccessMapInterface)
    assert AccessMapInterface in type(_map()).__mro__
