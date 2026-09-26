from __future__ import annotations

from xtr_cache_contracts import Metadata


def test_every_key_is_optional_so_a_pool_may_record_none() -> None:
    assert Metadata.__required_keys__ == frozenset()
    assert Metadata.__optional_keys__ == {"expiry", "ctime", "tags", "save_failed"}
