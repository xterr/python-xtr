"""What a handler recorded on a request, held to a regular expression."""

from __future__ import annotations

import pytest
from xtr_http_message import ServerRequest

from xtr_http_foundation import AttributesRequestMatcher
from xtr_http_foundation.exception import InvalidArgumentError


def _recorded() -> ServerRequest:
    """A request carrying one text attribute and one that is not text."""
    return (
        ServerRequest("GET", "/admin/foo")
        .with_attribute("foo", "foo_bar")
        .with_attribute("_controller", _recorded)
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("key", "regexp", "expected"),
    [
        ("foo", "foo_.*", True),
        ("foo", "foo", True),
        ("foo", "^foo_bar$", True),
        ("foo", "babar", False),
        # The attribute holds a callable rather than text, so nothing is matched against.
        ("_controller", "babar", False),
    ],
)
async def test_it_matches_an_attribute(key: str, regexp: str, expected: bool) -> None:
    matcher = AttributesRequestMatcher({key: regexp})

    assert await matcher.matches(_recorded()) is expected


@pytest.mark.anyio
async def test_it_refuses_a_request_carrying_no_such_attribute() -> None:
    matcher = AttributesRequestMatcher({"missing": ".*"})

    assert await matcher.matches(_recorded()) is False


@pytest.mark.anyio
async def test_it_claims_every_request_when_it_holds_no_expression() -> None:
    matcher = AttributesRequestMatcher({})

    assert await matcher.matches(_recorded()) is True


@pytest.mark.anyio
async def test_it_matches_every_expression_it_holds() -> None:
    matcher = AttributesRequestMatcher({"foo": "^foo_", "missing": ".*"})

    assert await matcher.matches(_recorded()) is False


def test_it_refuses_an_expression_that_does_not_read_as_one() -> None:
    with pytest.raises(InvalidArgumentError, match=r'"\(unclosed" is not a valid'):
        _ = AttributesRequestMatcher({"foo": "(unclosed"})
