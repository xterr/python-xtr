from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_request import FakeRequest
from tests.support.fake_server_request import FakeServerRequest
from tests.support.missing_member import members_of, without
from tests.support.parameter_default import default_of
from xtr_http_message_contracts import (
    MessageInterface,
    RequestInterface,
    ServerRequestInterface,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_a_fake_carrying_every_member_is_a_server_request() -> None:
    request: ServerRequestInterface = FakeServerRequest()

    assert isinstance(request, ServerRequestInterface)


def test_a_server_request_is_also_a_request_and_a_message() -> None:
    request = FakeServerRequest()

    assert isinstance(request, RequestInterface)
    assert isinstance(request, MessageInterface)


@pytest.mark.parametrize("missing", sorted(members_of(FakeServerRequest)))
def test_a_fake_missing_a_member_is_not_a_server_request(missing: str) -> None:
    assert not isinstance(without(FakeServerRequest, missing)(), ServerRequestInterface)


def test_a_request_alone_is_not_a_server_request() -> None:
    assert not isinstance(FakeRequest(), ServerRequestInterface)


@pytest.mark.parametrize(
    ("method", "parameter", "expected"),
    [(ServerRequestInterface.get_attribute, "default", None)],
)
def test_an_optional_argument_has_the_documented_default(
    method: Callable[..., object], parameter: str, expected: object
) -> None:
    assert default_of(method, parameter) == expected
