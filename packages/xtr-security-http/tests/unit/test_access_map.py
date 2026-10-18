"""The access map finds the attributes and the channel of the first rule a request matches."""

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

    assert await _map().get_patterns(message) == (("ROLE_ADMIN",), None)


async def test_a_broader_rule_matches_when_the_narrow_one_does_not() -> None:
    message = make_message(path="/api/books")

    assert await _map().get_patterns(message) == (("IS_AUTHENTICATED",), None)


async def test_no_rule_matches_answers_no_attributes_and_no_channel() -> None:
    message = make_message(path="/public")

    assert await _map().get_patterns(message) == ((), None)


async def test_an_empty_map_matches_nothing() -> None:
    message = make_message(path="/api")

    assert await AccessMap().get_patterns(message) == ((), None)


async def test_the_attribute_rides_out_as_the_one_member_of_a_tuple() -> None:
    message = make_message(path="/api/admin/panel")

    attributes, _channel = await _map().get_patterns(message)

    assert attributes == ("ROLE_ADMIN",)
    assert isinstance(attributes, tuple)


def test_the_map_satisfies_its_interface() -> None:
    assert isinstance(_map(), AccessMapInterface)
    assert AccessMapInterface in type(_map()).__mro__
