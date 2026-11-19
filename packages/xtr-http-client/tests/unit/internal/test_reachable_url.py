from __future__ import annotations

import pytest

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.reachable_url import reachable_url


def test_a_host_named_in_another_script_is_rewritten_to_the_form_that_reaches_it() -> None:
    assert reachable_url("http://Bücher.example:8057/") == "http://xn--bcher-kva.example:8057/"


def test_an_ascii_url_is_left_exactly_as_it_was_given() -> None:
    assert reachable_url("http://foo:b%3Dar@localhost:8057/a?b=c") == (
        "http://foo:b%3Dar@localhost:8057/a?b=c"
    )


def test_a_host_no_name_server_could_hold_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="for "):
        _ = reachable_url("http://" + "ü" * 100 + ".example/")
