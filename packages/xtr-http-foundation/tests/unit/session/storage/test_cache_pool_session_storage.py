"""The session storage that keeps its entries in a cache pool."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

import pytest
from xtr_cache_contracts import CacheError, ItemInterface, Metadata

from xtr_http_foundation import Session, SessionStorageInterface
from xtr_http_foundation.exception import InvalidArgumentError, SessionError
from xtr_http_foundation.session.storage.cache_pool_session_storage import CachePoolSessionStorage

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime, timedelta

_ID = "0123456789abcdef" * 3
_KEY = f"session.{_ID}"


@final
class FakeItem:
    """One entry as the fake pool hands it out: hit or miss, expired by hand.

    Answers the item contract the way a pool that stores no tags and no
    metadata does: ``tag`` raises, as the contract says it may, and
    ``metadata`` is always empty.
    """

    __slots__ = ("_key", "hit", "ttl", "value")

    def __init__(self, key: str, *, value: object = None, hit: bool = False) -> None:
        self._key = key
        self.value = value
        self.hit = hit
        self.ttl: float | timedelta | None = None

    @property
    def key(self) -> str:
        """The key the entry is stored under."""
        return self._key

    def get(self) -> object:
        """Return the value; ``None`` when the entry is not a hit."""
        return self.value

    def is_hit(self) -> bool:
        """Tell whether the pool held a value for the key when the entry was looked up."""
        return self.hit

    def set(self, value: object, /) -> Self:
        """Set the value to save."""
        self.value = value
        return self

    def expires_after(self, ttl: float | timedelta | None, /) -> Self:
        """Record the lifetime the entry was asked to live."""
        self.ttl = ttl
        return self

    def expires_at(self, expiration: datetime | None, /) -> Self:
        """Accept the moment form of a lifetime; the fake counts only the relative one."""
        del expiration
        return self

    def tag(self, tags: str | Iterable[str], /) -> Self:
        """Refuse a tag: the fake pool stores none.

        Raises:
            CacheError: Always — the pool this entry comes from stores no tags.
        """
        del tags
        raise CacheError("The fake pool stores no tags.")

    @property
    def metadata(self) -> Metadata:
        """Return nothing: the fake pool stores no metadata."""
        return Metadata()


@final
class FakePool:
    """A pool the tests fill, expire and break by hand.

    Answers the pool contract the way a backend does: an entry it does not
    hold is a miss, one it holds but has expired is a miss too, an item of
    another kind is refused by ``save``, and a broken backend answers
    ``False`` rather than raising.
    """

    __slots__ = ("backend_fails", "entries")

    def __init__(self) -> None:
        self.entries: dict[str, FakeItem] = {}
        self.backend_fails = False

    async def get_item(self, key: str, /) -> FakeItem:
        """Return the entry for ``key``, a hit or a miss."""
        entry = self.entries.get(key)
        if entry is not None and entry.hit:
            return entry

        return FakeItem(key)

    async def get_items(self, keys: Iterable[str], /) -> Mapping[str, FakeItem]:
        """Return an entry for each key, hits and misses alike."""
        return {key: await self.get_item(key) for key in keys}

    async def has_item(self, key: str, /) -> bool:
        """Tell whether the pool holds an unexpired value for ``key``."""
        entry = self.entries.get(key)
        return entry is not None and entry.hit

    async def clear(self, prefix: str = "") -> bool:
        """Remove every entry whose key starts with ``prefix``."""
        self.entries = {
            key: entry for key, entry in self.entries.items() if not key.startswith(prefix)
        }
        return True

    async def delete_item(self, key: str, /) -> bool:
        """Remove the entry under ``key``; a key holding nothing is fine."""
        _ = self.entries.pop(key, None)
        return not self.backend_fails

    async def delete_items(self, keys: Iterable[str], /) -> bool:
        """Remove the entries under ``keys``."""
        removed = True
        for key in keys:
            removed = await self.delete_item(key) and removed
        return removed

    async def save(self, item: ItemInterface, /) -> bool:
        """Store ``item`` now, if it is one this pool hands out.

        Returns:
            ``False`` when the item is of another kind, or when the backend
            is broken for the test; ``True`` otherwise.
        """
        if not isinstance(item, FakeItem) or self.backend_fails:
            return False

        item.hit = True
        self.entries[item.key] = item
        return True

    async def save_deferred(self, item: ItemInterface, /) -> bool:
        """Accept an item for the next commit; the fake stores nothing deferred."""
        del item
        return True

    async def commit(self) -> bool:
        """Store every item queued by ``save_deferred`` — of which the fake keeps none."""
        return True


def test_it_answers_the_storage_contract() -> None:
    assert isinstance(CachePoolSessionStorage(FakePool()), SessionStorageInterface)


@pytest.mark.anyio
async def test_it_keeps_the_entry_under_the_pools_own_name_for_a_session() -> None:
    pool = FakePool()
    storage = CachePoolSessionStorage(pool)

    await storage.write(_ID, {"theme": "dark"}, ttl=None)

    assert list(pool.entries) == [_KEY]


@pytest.mark.anyio
async def test_it_writes_the_attributes_as_json_and_reads_them_back() -> None:
    pool = FakePool()
    storage = CachePoolSessionStorage(pool)

    await storage.write(_ID, {"theme": "dark", "visits": 3}, ttl=None)

    assert await storage.read(_ID) == {"theme": "dark", "visits": 3}
    assert pool.entries[_KEY].value == '{"theme": "dark", "visits": 3}'


@pytest.mark.anyio
async def test_it_reads_nothing_for_an_id_the_pool_does_not_hold() -> None:
    assert await CachePoolSessionStorage(FakePool()).read(_ID) is None


@pytest.mark.anyio
async def test_it_reads_nothing_once_the_pool_expired_the_entry() -> None:
    pool = FakePool()
    storage = CachePoolSessionStorage(pool)
    await storage.write(_ID, {"theme": "dark"}, ttl=None)
    pool.entries[_KEY].hit = False

    assert await storage.read(_ID) is None


@pytest.mark.anyio
async def test_it_reads_nothing_for_an_entry_that_no_longer_decodes() -> None:
    pool = FakePool()
    pool.entries[_KEY] = FakeItem(_KEY, value="{not json", hit=True)

    assert await CachePoolSessionStorage(pool).read(_ID) is None


@pytest.mark.anyio
async def test_it_reads_nothing_for_an_entry_that_is_not_what_it_writes() -> None:
    pool = FakePool()
    pool.entries[_KEY] = FakeItem(_KEY, value='["theme"]', hit=True)

    assert await CachePoolSessionStorage(pool).read(_ID) is None

    pool.entries[_KEY] = FakeItem(_KEY, value=42, hit=True)

    assert await CachePoolSessionStorage(pool).read(_ID) is None


@pytest.mark.anyio
async def test_it_expires_the_entry_by_the_ttl_the_write_names() -> None:
    pool = FakePool()
    storage = CachePoolSessionStorage(pool)

    await storage.write(_ID, {"theme": "dark"}, ttl=60)

    assert pool.entries[_KEY].ttl == 60


@pytest.mark.anyio
async def test_it_expires_the_entry_by_its_own_default_when_the_write_names_none() -> None:
    pool = FakePool()
    storage = CachePoolSessionStorage(pool, ttl=900)

    await storage.write(_ID, {"theme": "dark"}, ttl=None)

    assert pool.entries[_KEY].ttl == 900


@pytest.mark.anyio
async def test_it_expires_the_entry_by_twenty_four_minutes_when_nothing_is_said() -> None:
    pool = FakePool()

    await CachePoolSessionStorage(pool).write(_ID, {"theme": "dark"}, ttl=None)

    assert pool.entries[_KEY].ttl == 1440


@pytest.mark.parametrize(
    "value",
    [{1, 2}, (1, 2), {1: "one"}, object(), float("nan"), b"ab"],
)
@pytest.mark.anyio
async def test_it_refuses_a_value_that_cannot_round_trip(value: object) -> None:
    storage = CachePoolSessionStorage(FakePool())

    with pytest.raises(InvalidArgumentError):
        await storage.write(_ID, {"theme": value}, ttl=None)


@pytest.mark.anyio
async def test_it_refuses_at_save_when_a_value_cannot_round_trip() -> None:
    session = Session(CachePoolSessionStorage(FakePool()))

    await session.set("theme", {1, 2})

    with pytest.raises(InvalidArgumentError):
        await session.save()


@pytest.mark.anyio
async def test_it_raises_when_the_pool_cannot_keep_the_entry() -> None:
    pool = FakePool()
    pool.backend_fails = True

    with pytest.raises(SessionError):
        await CachePoolSessionStorage(pool).write(_ID, {"theme": "dark"}, ttl=None)


@pytest.mark.anyio
async def test_it_raises_when_the_pool_cannot_remove_the_entry() -> None:
    pool = FakePool()
    pool.backend_fails = True

    with pytest.raises(SessionError):
        await CachePoolSessionStorage(pool).delete(_ID)


@pytest.mark.anyio
async def test_it_removes_the_entry() -> None:
    pool = FakePool()
    storage = CachePoolSessionStorage(pool)
    await storage.write(_ID, {"theme": "dark"}, ttl=None)

    await storage.delete(_ID)

    assert await storage.read(_ID) is None


@pytest.mark.anyio
async def test_it_removes_an_id_the_pool_does_not_hold_without_complaint() -> None:
    storage = CachePoolSessionStorage(FakePool())

    await storage.delete(_ID)

    assert await storage.read(_ID) is None
