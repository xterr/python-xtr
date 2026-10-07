from __future__ import annotations

import xtr_password_hasher
from xtr_password_hasher import bcrypt_available, create_auto_password_hasher
from xtr_password_hasher import hasher as hasher_package
from xtr_password_hasher.hasher import migrating_password_hasher


def test_the_root_exports_the_auto_hasher_builder_and_the_bcrypt_probe() -> None:
    assert "create_auto_password_hasher" in xtr_password_hasher.__all__
    assert "bcrypt_available" in xtr_password_hasher.__all__
    assert callable(create_auto_password_hasher)
    assert callable(bcrypt_available)


def test_the_hasher_package_exports_the_auto_hasher_builder_and_the_bcrypt_probe() -> None:
    assert "create_auto_password_hasher" in hasher_package.__all__
    assert "bcrypt_available" in hasher_package.__all__
    assert callable(hasher_package.create_auto_password_hasher)
    assert callable(hasher_package.bcrypt_available)


def test_the_salt_helpers_are_in_the_migrating_module_all() -> None:
    assert "hash_with_salt" in migrating_password_hasher.__all__
    assert "verify_with_salt" in migrating_password_hasher.__all__
