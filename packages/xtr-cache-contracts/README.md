<div align="center">

# xtr-cache-contracts

**The caching contract, and nothing else — so a library that caches installs nothing else.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="core dependencies: 2" src="https://img.shields.io/badge/core%20deps-2-3FB950">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A library that caches should not decide where values go. It takes a `CacheInterface`, hands it a
key and the function that computes the value, and leaves memory, files or a server to the
application that wires it.

That needs the *contract*, not a backend. This package is that dependency, reduced to what the
seam is made of:

- 🔁 **`CacheInterface`** — fetch-or-compute in one call, and delete.
- 🏷️ **`TagAwareCacheInterface`** — drop every value carrying a tag, whatever its key.
- 🗃️ **`CacheItemPoolInterface`** — the items underneath: hits told apart from misses, several
  keys per round trip, batched writes.
- 📁 **`NamespacedPoolInterface`** — a view of a pool confined to a sub-namespace.
- 🧩 **`CacheMixin`** — `CacheInterface` for free on any pool, with early recomputation.
- 🪶 **Two small dependencies** — `typing-extensions`, for `@override` on 3.11, and
  `xtr-clock`, which has none of its own.

```python
from xtr_cache_contracts import CacheInterface, ItemInterface


class Profiles:
    def __init__(self, cache: CacheInterface) -> None:
        self._cache = cache

    async def get(self, user_id: int) -> Profile:
        async def load(item: ItemInterface) -> Profile:
            item.expires_after(3600)
            return await fetch_profile(user_id)

        return await self._cache.get(f"profile.{user_id}", load)
```

## Install

```sh
uv add xtr-cache-contracts
```

Requires Python 3.11+.

## Who installs what

|  | Depends on |
| --- | --- |
| **A library that caches** | `xtr-cache-contracts` at runtime. |
| **An application** | `xtr-cache`, which implements this contract with adapters and wires pools from configuration. |

`xtr-cache` **re-exports** every symbol here rather than redefining it, so
`xtr_cache.CacheInterface is xtr_cache_contracts.CacheInterface`. That identity is what lets a
container register a pool under the interface and a library, which never imported `xtr-cache`,
receive it.

## Fetch-or-compute

```python
class CacheInterface(Protocol):
    async def get(
        self,
        key: str,
        callback: Callback[T],
        /,
        *,
        beta: float | None = None,
        metadata: Metadata | None = None,
    ) -> T: ...

    async def delete(self, key: str, /) -> bool: ...
```

On a miss, `callback` is awaited with the item for `key`; what it returns is saved and returned.
On a hit, the stored value comes back as the type `callback` returns — keep one key for one type.

Checking for a value, computing it and saving it is three steps with a race between each. Handing
the cache the computation instead lets it decide when to run it, which is what makes stampede
protection possible: computing a missing key once for every caller waiting on it, or refreshing
a value just before it expires.

- **The callback** is any `async def` taking the item, or an object with an `async def __call__`.
  It sets the value's lifetime and tags through the item. If it raises, nothing is stored and
  the error reaches the caller unchanged.
- **`beta`** controls early recomputation. A hit whose metadata says when it expires and how long
  it took to compute may be recomputed before it expires, with a chance that grows as expiry
  nears and as `beta` grows. `0` disables it, `math.inf` forces recomputation now, and `None`
  leaves the choice to the implementation (`1.0` in `CacheMixin`).
- **`metadata`** is a dict the cache fills: `expiry` (Unix timestamp), `ctime` (milliseconds the
  value took to compute), `tags`, and `save_failed` when a computed value could not be stored.

```python
from xtr_cache_contracts import Metadata

metadata: Metadata = {}
report = await cache.get("report.daily", build_report, metadata=metadata)
if metadata.get("save_failed"):
    ...
```

## Items and pools

`CacheItemPoolInterface` is the level below: for code that needs a hit told apart from a miss,
several keys in one round trip, or writes batched until `commit()` — and the level a backend
implements.

```python
item = await pool.get_item("rate.42")
if not item.is_hit():
    await pool.save(item.set(0).expires_after(60))

items = await pool.get_items(["a", "b", "c"])  # every key, hit or miss, in the order asked
await pool.save_deferred(item)  # queued ...
await pool.commit()  # ... stored
```

An item is returned for every key, found or not, so `None` is a value like any other. Changing
an item reaches the backend only once it is saved back into the pool that handed it out.

The rules:

- **Keys** are non-empty strings without any of `{}()/\@:` (`RESERVED_CHARACTERS`). Letters,
  digits, `_` and `.` up to 64 characters work everywhere; a pool may accept more. Tags follow
  the same rules.
- **A backend failure never raises.** The call returns `False`, or reads as a miss, and the
  implementation logs it: code that caches keeps working when the cache does not. What raises
  is a mistake in the calling code — an invalid key, a tag on an item whose pool cannot store
  tags.
- **Lifetimes** are set on the item: `expires_after(seconds or timedelta)` or
  `expires_at(datetime)`. `None` falls back to the pool's default; a lifetime of zero or less
  removes the key when the item is saved.
- **Deferred items** are committed by `commit()`, or before their key is read from the same pool.
  Nothing commits them when the pool is discarded.

## Tags and namespaces

A tag-aware cache drops values by tag rather than by key. Tag a value when computing it:

```python
async def load_invoice(item: ItemInterface) -> Invoice:
    item.tag([f"customer.{customer_id}", "invoices"])
    return await fetch_invoice(invoice_id)


await cache.get(f"invoice.{invoice_id}", load_invoice)
await cache.invalidate_tags([f"customer.{customer_id}"])  # every invoice of that customer
```

A namespaced pool hands out a view of itself whose keys live under a sub-namespace, so a group of
keys can be cleared together: `pool.with_sub_namespace("tenant42")`. The original pool is left as
it was. Tags ignore sub-namespaces.

## Implementing a pool

Implement `CacheItemPoolInterface` and derive from `CacheMixin` to get `get()` and `delete()`
built on your `get_item()`, `save()` and `delete_item()`:

```python
from xtr_cache_contracts import CacheItemPoolInterface, CacheMixin


class MyPool(CacheItemPoolInterface, CacheMixin): ...
```

`CacheMixin` computes a miss, saves it, reports a failed save in `metadata`, and recomputes a hit
early when its metadata allows. It reads the time from the clock in force (`xtr_clock.now()`),
so `mock_time()` or a `MockClock` installed by a test freezes it too. It does not make concurrent misses on one key compute once — that
needs a lock or a shared in-flight computation, and is the implementation's to add by overriding
`get()`.

## What is not here

Everything that stores or acts on values: the item class, adapters for memory, files and Redis,
serialisation, stampede locking, chaining, and the bundle. All of that is
[xtr-cache](https://github.com/xterr/python-xtr-cache).

There is no simple key-value interface (`get(key, default)` / `set(key, value, ttl)`): it cannot
tell a cached `None` from a miss, and checking then reading is a race. Fetch-or-compute covers the
common case, and the item pool covers the rest.

## Errors

| Error | Raised when |
| --- | --- |
| `CacheError` | Never directly — the base every caching error derives from, `xtr-cache`'s included, such as the one `tag()` raises on an item whose pool cannot store tags |
| `InvalidArgumentError` | A key, a tag, a namespace or `beta` is invalid (also a `ValueError`); what is wrong is in `reason` |

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-cache-contracts`; run the commands below from there. The
`python-xtr-cache-contracts` repository is a read-only copy, so send issues and pull requests to
the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
