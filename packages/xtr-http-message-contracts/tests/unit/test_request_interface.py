from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_message import FakeMessage
from tests.support.fake_request import FakeRequest
from tests.support.missing_member import members_of, without
from tests.support.parameter_default import default_of
from xtr_http_message_contracts import MessageInterface, RequestInterface

if TYPE_CHECKING:
    from collections.abc import Callable


def test_a_fake_carrying_every_member_is_a_request() -> None:
    request: RequestInterface = FakeRequest()

    assert isinstance(request, RequestInterface)


def test_a_request_is_also_a_message() -> None:
    assert isinstance(FakeRequest(), MessageInterface)


@pytest.mark.parametrize("missing", sorted(members_of(FakeRequest)))
def test_a_fake_missing_a_member_is_not_a_request(missing: str) -> None:
    assert not isinstance(without(FakeRequest, missing)(), RequestInterface)


def test_a_message_alone_is_not_a_request() -> None:
    assert not isinstance(FakeMessage(), RequestInterface)


@pytest.mark.parametrize(
    ("method", "parameter", "expected"),
    [(RequestInterface.with_uri, "preserve_host", False)],
)
def test_an_optional_argument_has_the_documented_default(
    method: Callable[..., object], parameter: str, expected: object
) -> None:
    assert default_of(method, parameter) == expected
