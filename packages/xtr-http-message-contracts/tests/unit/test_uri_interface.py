from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_uri import FakeUri
from tests.support.missing_member import members_of, without
from tests.support.parameter_default import default_of
from xtr_http_message_contracts import UriInterface

if TYPE_CHECKING:
    from collections.abc import Callable


def test_a_fake_carrying_every_member_is_a_uri() -> None:
    uri: UriInterface = FakeUri()

    assert isinstance(uri, UriInterface)


@pytest.mark.parametrize("missing", sorted(members_of(FakeUri)))
def test_a_fake_missing_a_member_is_not_a_uri(missing: str) -> None:
    assert not isinstance(without(FakeUri, missing)(), UriInterface)


def test_a_plain_object_is_not_a_uri() -> None:
    assert not isinstance(object(), UriInterface)


@pytest.mark.parametrize(
    ("method", "parameter", "expected"),
    [(UriInterface.with_user_info, "password", None)],
)
def test_an_optional_argument_has_the_documented_default(
    method: Callable[..., object], parameter: str, expected: object
) -> None:
    assert default_of(method, parameter) == expected
