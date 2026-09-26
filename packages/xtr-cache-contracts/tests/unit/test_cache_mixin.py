from __future__ import annotations

import math
from typing import TYPE_CHECKING, TypeVar, final

import pytest
from typing_extensions import override
from xtr_clock.testing import mock_time

from tests.support.in_memory_pool import InMemoryItem, InMemoryPool
from xtr_cache_contracts import CacheInterface, InvalidArgumentError, ItemInterface, Metadata
from xtr_cache_contracts import cache_mixin as cache_mixin_module

if TYPE_CHECKING:
    from xtr_cache_contracts import Callback

pytestmark = pytest.mark.anyio

NOON = "2024-04-09 12:00:00"

_T = TypeVar("_T")


@final
class Computation:
    """Counts its calls and returns what it was told to."""

    def __init__(self, value: object = "computed") -> None:
        self.value = value
        self.items: list[ItemInterface] = []

    async def __call__(self, item: ItemInterface) -> object:
        self.items.append(item)
        return self.value


def test_a_pool_deriving_from_it_is_a_cache() -> None:
    assert isinstance(InMemoryPool(), CacheInterface)


async def test_a_miss_is_computed_saved_and_returned() -> None:
    pool = InMemoryPool()
    compute = Computation()

    value = await pool.get("k", compute)

    assert value == "computed"
    assert [item.key for item in compute.items] == ["k"]
    assert (await pool.get_item("k")).get() == "computed"


async def test_a_hit_is_returned_without_computing() -> None:
    pool = InMemoryPool()
    _ = await pool.get("k", Computation("first"))
    compute = Computation("second")

    assert await pool.get("k", compute) == "first"
    assert compute.items == []


async def test_a_cached_none_is_a_hit() -> None:
    pool = InMemoryPool()
    _ = await pool.get("k", Computation(None))
    compute = Computation()

    assert await pool.get("k", compute) is None
    assert compute.items == []


async def test_the_callback_sets_the_lifetime_through_the_item() -> None:
    pool = InMemoryPool()

    async def compute(item: ItemInterface) -> int:
        _ = item.expires_after(10)
        return 1

    with mock_time(NOON) as clock:
        _ = await pool.get("k", compute)
        clock.sleep(10)

        assert not await pool.has_item("k")


async def test_an_infinite_beta_recomputes_a_hit() -> None:
    pool = InMemoryPool()
    _ = await pool.get("k", Computation("old"))

    assert await pool.get("k", Computation("new"), beta=math.inf) == "new"
    assert (await pool.get_item("k")).get() == "new"


@pytest.mark.parametrize("beta", [-0.1, math.nan])
async def test_a_negative_or_undefined_beta_is_refused(beta: float) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = await InMemoryPool().get("k", Computation(), beta=beta)

    assert "beta" in raised.value.reason


async def test_a_value_that_cannot_be_saved_is_still_returned_and_reported() -> None:
    pool = InMemoryPool()
    pool.fail_saves = True
    metadata: Metadata = {}

    assert await pool.get("k", Computation(), metadata=metadata) == "computed"
    assert metadata == {"save_failed": True}


async def test_a_raising_callback_stores_nothing() -> None:
    pool = InMemoryPool()

    async def fail(item: ItemInterface) -> int:
        raise LookupError(item.key)

    with pytest.raises(LookupError):
        _ = await pool.get("k", fail)

    assert not await pool.has_item("k")


async def test_the_metadata_of_a_hit_is_reported() -> None:
    pool = InMemoryPool()
    pool.seed("k", 1, {"ctime": 5, "tags": ("a",)})
    metadata: Metadata = {}

    _ = await pool.get("k", Computation(), metadata=metadata)

    assert metadata == {"ctime": 5, "tags": ("a",)}


async def test_a_hit_close_to_expiry_is_recomputed_early(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mixin_module, "_draw", lambda: 0.1)  # -ln(0.1) ≈ 2.3
    pool = InMemoryPool()
    compute = Computation("fresh")

    with mock_time(NOON) as clock:
        pool.seed("k", "stale", {"expiry": clock.now().timestamp() + 0.5, "ctime": 1000})

        assert await pool.get("k", compute) == "fresh"

    assert isinstance(elected := compute.items[0], InMemoryItem)
    assert elected.expiry is None


async def test_a_hit_far_from_expiry_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mixin_module, "_draw", lambda: 0.9)  # -ln(0.9) ≈ 0.1
    pool = InMemoryPool()

    with mock_time(NOON) as clock:
        pool.seed("k", "stale", {"expiry": clock.now().timestamp() + 0.5, "ctime": 1000})

        assert await pool.get("k", Computation("fresh")) == "stale"


async def test_a_zero_beta_never_recomputes_early(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mixin_module, "_draw", lambda: 1e-300)
    pool = InMemoryPool()

    with mock_time(NOON) as clock:
        pool.seed("k", "stale", {"expiry": clock.now().timestamp() + 0.001, "ctime": 60_000})

        assert await pool.get("k", Computation("fresh"), beta=0) == "stale"


async def test_a_hit_without_timing_metadata_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_mixin_module, "_draw", lambda: 1e-300)
    pool = InMemoryPool()
    pool.seed("k", "stale", {"tags": ("a",)})

    assert await pool.get("k", Computation("fresh")) == "stale"


async def test_a_random_draw_of_zero_is_not_a_domain_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cache_mixin_module, "random", lambda: 0.0)
    pool = InMemoryPool()

    with mock_time(NOON) as clock:
        pool.seed("k", "stale", {"expiry": clock.now().timestamp() + 0.5, "ctime": 1000})

        assert await pool.get("k", Computation("fresh")) == "stale"


async def test_deleting_removes_the_value() -> None:
    pool = InMemoryPool()
    _ = await pool.get("k", Computation())

    assert await pool.delete("k")

    assert not await pool.has_item("k")


@final
class _HookedPool(InMemoryPool):
    """Overrides the three steps of ``get``, recording what each was given."""

    def __init__(self, now: float) -> None:
        super().__init__()
        self.now = now
        self.computed: list[tuple[str, float]] = []
        self.elected: list[tuple[str, float]] = []

    @override
    async def _compute(
        self,
        item: ItemInterface,
        callback: Callback[_T],
        beta: float,
        metadata: Metadata | None,
    ) -> _T:
        self.computed.append((item.key, beta))
        return await super()._compute(item, callback, beta, metadata)

    @override
    def _now(self) -> float:
        return self.now

    @override
    def _on_elected(self, item: ItemInterface, remaining: float) -> None:
        self.elected.append((item.key, remaining))


async def test_a_pool_adjusts_how_values_are_computed_timed_and_elected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cache_mixin_module, "_draw", lambda: 0.1)
    with mock_time(NOON) as clock:
        now = clock.now().timestamp()
        pool = _HookedPool(now=now)
        pool.seed("k", "stale", {"expiry": now + 0.5, "ctime": 1000})

        assert await pool.get("k", Computation("fresh"), beta=2.0) == "fresh"

    assert pool.computed == [("k", 2.0)]
    assert pool.elected == [("k", 0.5)]
