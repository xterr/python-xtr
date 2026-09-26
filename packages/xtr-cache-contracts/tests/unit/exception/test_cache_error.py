from __future__ import annotations

from xtr_cache_contracts import CacheError, InvalidArgumentError


def test_every_contract_error_derives_from_it() -> None:
    assert issubclass(InvalidArgumentError, CacheError)
