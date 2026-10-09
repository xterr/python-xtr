from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_message import FakeMessage
from tests.support.fake_response import FakeResponse
from tests.support.missing_member import members_of, without
from tests.support.parameter_default import default_of
from xtr_http_message_contracts import MessageInterface, ResponseInterface

if TYPE_CHECKING:
    from collections.abc import Callable


def test_a_fake_carrying_every_member_is_a_response() -> None:
    response: ResponseInterface = FakeResponse()

    assert isinstance(response, ResponseInterface)


def test_a_response_is_also_a_message() -> None:
    assert isinstance(FakeResponse(), MessageInterface)


@pytest.mark.parametrize("missing", sorted(members_of(FakeResponse)))
def test_a_fake_missing_a_member_is_not_a_response(missing: str) -> None:
    assert not isinstance(without(FakeResponse, missing)(), ResponseInterface)


def test_a_message_alone_is_not_a_response() -> None:
    assert not isinstance(FakeMessage(), ResponseInterface)


@pytest.mark.parametrize(
    ("method", "parameter", "expected"),
    [(ResponseInterface.with_status, "reason_phrase", "")],
)
def test_an_optional_argument_has_the_documented_default(
    method: Callable[..., object], parameter: str, expected: object
) -> None:
    assert default_of(method, parameter) == expected
