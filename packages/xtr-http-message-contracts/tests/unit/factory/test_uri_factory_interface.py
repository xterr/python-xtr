from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_uri import FakeUri
from tests.support.missing_member import members_of, without
from tests.support.parameter_default import default_of
from xtr_http_message_contracts import UriFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_message_contracts import UriInterface


class _FakeUriFactory:
    def create_uri(self, uri: str = "") -> UriInterface:
        del uri
        return FakeUri()


def test_a_fake_carrying_every_member_is_a_uri_factory() -> None:
    factory: UriFactoryInterface = _FakeUriFactory()

    assert isinstance(factory, UriFactoryInterface)


@pytest.mark.parametrize("missing", sorted(members_of(_FakeUriFactory)))
def test_a_fake_missing_a_member_is_not_a_uri_factory(missing: str) -> None:
    assert not isinstance(without(_FakeUriFactory, missing)(), UriFactoryInterface)


def test_a_plain_object_is_not_a_uri_factory() -> None:
    assert not isinstance(object(), UriFactoryInterface)


@pytest.mark.parametrize(
    ("method", "parameter", "expected"),
    [(UriFactoryInterface.create_uri, "uri", "")],
)
def test_an_optional_argument_has_the_documented_default(
    method: Callable[..., object], parameter: str, expected: object
) -> None:
    assert default_of(method, parameter) == expected
