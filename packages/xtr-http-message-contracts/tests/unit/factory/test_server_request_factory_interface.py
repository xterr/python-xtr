from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_server_request import FakeServerRequest
from tests.support.missing_member import members_of, without
from tests.support.parameter_default import default_of
from xtr_http_message_contracts import ServerRequestFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_http_message_contracts import ServerRequestInterface, UriInterface


class _FakeServerRequestFactory:
    def create_server_request(
        self,
        method: str,
        uri: UriInterface | str,
        server_params: Mapping[str, object] | None = None,
    ) -> ServerRequestInterface:
        del method, uri, server_params
        return FakeServerRequest()


def test_a_fake_carrying_every_member_is_a_server_request_factory() -> None:
    factory: ServerRequestFactoryInterface = _FakeServerRequestFactory()

    assert isinstance(factory, ServerRequestFactoryInterface)


@pytest.mark.parametrize("missing", sorted(members_of(_FakeServerRequestFactory)))
def test_a_fake_missing_a_member_is_not_a_server_request_factory(missing: str) -> None:
    assert not isinstance(
        without(_FakeServerRequestFactory, missing)(), ServerRequestFactoryInterface
    )


def test_a_plain_object_is_not_a_server_request_factory() -> None:
    assert not isinstance(object(), ServerRequestFactoryInterface)


@pytest.mark.parametrize(
    ("method", "parameter", "expected"),
    [(ServerRequestFactoryInterface.create_server_request, "server_params", None)],
)
def test_an_optional_argument_has_the_documented_default(
    method: Callable[..., object], parameter: str, expected: object
) -> None:
    assert default_of(method, parameter) == expected
