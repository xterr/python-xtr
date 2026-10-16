"""The storages are reachable from the folder that groups them and from the package."""

from __future__ import annotations

import xtr_http_foundation
from xtr_http_foundation.session import storage

_STORAGES = ("MemorySessionStorage", "SessionStorageInterface")


def test_the_folder_exports_the_storages_that_need_no_extra() -> None:
    assert sorted(storage.__all__) == sorted(_STORAGES)


def test_the_package_exports_the_same_storages() -> None:
    for name in _STORAGES:
        assert getattr(xtr_http_foundation, name) is getattr(storage, name)


def test_the_cache_pool_storage_is_reached_by_name_not_by_export() -> None:
    # The cache-pool storage needs the ``cache`` extra, so importing it — not
    # importing the folder — is what turns the extra on.
    assert "CachePoolSessionStorage" not in storage.__all__
