from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_response import FakeResponse
from tests.support.missing_member import members_of, without
from tests.support.parameter_default import default_of
from xtr_http_message_contracts import ResponseFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_message_contracts import ResponseInterface


class _FakeResponseFactory:
    def create_response(
        self, code: int = 200, reason_phrase: str | None = None
    ) -> ResponseInterface:
        del code, reason_phrase
        return FakeResponse()


def test_a_fake_carrying_every_member_is_a_response_factory() -> None:
    factory: ResponseFactoryInterface = _FakeResponseFactory()

    assert isinstance(factory, ResponseFactoryInterface)


@pytest.mark.parametrize("missing", sorted(members_of(_FakeResponseFactory)))
def test_a_fake_missing_a_member_is_not_a_response_factory(missing: str) -> None:
    assert not isinstance(without(_FakeResponseFactory, missing)(), ResponseFactoryInterface)


def test_a_plain_object_is_not_a_response_factory() -> None:
    assert not isinstance(object(), ResponseFactoryInterface)


@pytest.mark.parametrize(
    ("method", "parameter", "expected"),
    [
        (ResponseFactoryInterface.create_response, "code", 200),
        (ResponseFactoryInterface.create_response, "reason_phrase", None),
    ],
)
def test_an_optional_argument_has_the_documented_default(
    method: Callable[..., object], parameter: str, expected: object
) -> None:
    assert default_of(method, parameter) == expected


def test_nothing_given_is_told_apart_from_no_phrase_asked_for() -> None:
    # `None` lets the factory fill the recommended phrase in; `""` asks for a
    # response carrying no phrase at all. A default of `""` could not tell
    # the two requests apart, so the default has to be `None`.
    assert default_of(ResponseFactoryInterface.create_response, "reason_phrase") is None
