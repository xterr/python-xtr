"""The key-loader interface is runtime-checkable against the real loader."""

from __future__ import annotations

from tests.support.keys import RSA_PRIVATE_PEM
from xtr_security_jwt.services.key_loader.key_loader_interface import (
    TYPE_PRIVATE,
    TYPE_PUBLIC,
    KeyLoaderInterface,
)
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader


def test_the_key_type_constants_are_distinct() -> None:
    assert TYPE_PUBLIC != TYPE_PRIVATE


def test_the_real_loader_satisfies_the_interface() -> None:
    assert isinstance(RawKeyLoader(RSA_PRIVATE_PEM, None), KeyLoaderInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), KeyLoaderInterface)
