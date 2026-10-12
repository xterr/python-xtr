"""Carrying parameters to where a browser is being sent."""

from __future__ import annotations

from typing import Final

from xtr_security_oauth2_server._redirect_uri import NO_PARAMS, redirect_uri_carrying

_URI: Final = "https://client.test/callback"


def test_a_parameter_is_carried_in_the_query() -> None:
    assert redirect_uri_carrying(_URI, {"state": "abc"}) == f"{_URI}?state=abc"


def test_a_parameter_whose_value_is_absent_is_left_out() -> None:
    # A client reads ``state=`` as state it never sent.
    assert redirect_uri_carrying(_URI, {"state": None, "code": "xyz"}) == f"{_URI}?code=xyz"


def test_a_uri_that_already_carries_a_query_gets_another_parameter_joined_on() -> None:
    carried = redirect_uri_carrying(f"{_URI}?keep=1", {"state": "abc"})

    assert carried == f"{_URI}?keep=1&state=abc"


def test_a_fragment_is_asked_for_by_the_delimiter() -> None:
    # What an access token handed straight to a browser uses, so it never
    # reaches a server log.
    carried = redirect_uri_carrying(_URI, {"access_token": "t"}, "#")

    assert carried == f"{_URI}#access_token=t"


def test_a_fragment_that_already_exists_gets_another_parameter_joined_on() -> None:
    carried = redirect_uri_carrying(f"{_URI}#a=1", {"b": "2"}, "#")

    assert carried == f"{_URI}#a=1&b=2"


def test_a_number_is_carried_as_the_text_of_it() -> None:
    assert redirect_uri_carrying(_URI, {"expires_in": 3600}) == f"{_URI}?expires_in=3600"


def test_carrying_nothing_leaves_the_uri_with_an_empty_query() -> None:
    # The grants ask for this when the request named no state: the separator
    # is there, and whatever is appended next joins it.
    assert redirect_uri_carrying(_URI, NO_PARAMS) == f"{_URI}?"
