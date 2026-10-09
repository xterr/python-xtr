from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_request import FakeRequest
from tests.support.missing_member import members_of, without
from xtr_http_message_contracts import RequestFactoryInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import RequestInterface, UriInterface


class _FakeRequestFactory:
    def create_request(self, method: str, uri: UriInterface | str) -> RequestInterface:
        del method, uri
        return FakeRequest()


def test_a_fake_carrying_every_member_is_a_request_factory() -> None:
    factory: RequestFactoryInterface = _FakeRequestFactory()

    assert isinstance(factory, RequestFactoryInterface)


@pytest.mark.parametrize("missing", sorted(members_of(_FakeRequestFactory)))
def test_a_fake_missing_a_member_is_not_a_request_factory(missing: str) -> None:
    assert not isinstance(without(_FakeRequestFactory, missing)(), RequestFactoryInterface)


def test_a_plain_object_is_not_a_request_factory() -> None:
    assert not isinstance(object(), RequestFactoryInterface)
