"""The key-dumper interface is runtime-checkable against the real loader."""

from __future__ import annotations

from tests.support.keys import RSA_PRIVATE_PEM
from xtr_security_jwt.services.key_loader.key_dumper_interface import KeyDumperInterface
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader


def test_the_real_loader_satisfies_the_interface() -> None:
    assert isinstance(RawKeyLoader(RSA_PRIVATE_PEM, None), KeyDumperInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), KeyDumperInterface)
