"""The access map finds the attribute of the first rule a request matches."""

from __future__ import annotations

import pytest
from xtr_http_foundation import PathRequestMatcher

from tests.support.messages import make_message
from xtr_security_http.access_map import AccessMap
from xtr_security_http.access_map_interface import AccessMapInterface

pytestmark = pytest.mark.anyio


def _map() -> AccessMap:
    access_map = AccessMap()
    access_map.add(PathRequestMatcher(r"^/api/admin"), "ROLE_ADMIN")
    access_map.add(PathRequestMatcher(r"^/api"), "IS_AUTHENTICATED")
    return access_map


async def test_the_first_matching_rule_decides() -> None:
    message = make_message(path="/api/admin/panel")

    assert await _map().get_attribute(message) == "ROLE_ADMIN"


async def test_a_broader_rule_matches_when_the_narrow_one_does_not() -> None:
    message = make_message(path="/api/books")

    assert await _map().get_attribute(message) == "IS_AUTHENTICATED"


async def test_no_rule_matches_returns_none() -> None:
    message = make_message(path="/public")

    assert await _map().get_attribute(message) is None


async def test_an_empty_map_matches_nothing() -> None:
    message = make_message(path="/api")

    assert await AccessMap().get_attribute(message) is None


def test_the_map_satisfies_its_interface() -> None:
    assert isinstance(_map(), AccessMapInterface)
    assert AccessMapInterface in type(_map()).__mro__
