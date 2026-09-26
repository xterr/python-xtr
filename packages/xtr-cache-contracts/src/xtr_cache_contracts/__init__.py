"""The caching contract: what code that caches depends on, and nothing more.

Code that caches should not decide where values go. It takes a
:class:`CacheInterface` and hands it a key and the function that computes the
value; the application decides whether memory, files or a server sit behind
it — so depending on this package costs a library nothing but the contract.

```python
async def load_profile(item: ItemInterface) -> Profile:
    item.expires_after(3600)
    return await profiles.fetch(user_id)


profile = await cache.get(f"profile.{user_id}", load_profile)
```

Three levels, most code needing only the first:

- :class:`CacheInterface` — fetch-or-compute, and delete.
  :class:`TagAwareCacheInterface` adds invalidation by tag.
- :class:`CacheItemPoolInterface` — the items underneath: hits told apart
  from misses, reads of several keys at once, batched writes. What a backend
  implements; :class:`CacheMixin` builds :class:`CacheInterface` on it.
- :class:`NamespacedPoolInterface` — a view of a pool confined to a
  sub-namespace.

Every call that reaches a backend is awaited. Backends and everything that
acts on stored values — adapters, serialisation, stampede locks, the bundle —
are ``xtr-cache``, which implements this contract and re-exports it, so the
two are never two different objects.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .cache_interface import CacheInterface
from .cache_item_pool_interface import CacheItemPoolInterface
from .cache_mixin import CacheMixin
from .callback import Callback
from .exception import CacheError, InvalidArgumentError
from .item_interface import RESERVED_CHARACTERS, ItemInterface
from .metadata import Metadata
from .namespaced_pool_interface import NamespacedPoolInterface
from .tag_aware_cache_interface import TagAwareCacheInterface

try:
    __version__ = version("xtr-cache-contracts")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "RESERVED_CHARACTERS",
    "CacheError",
    "CacheInterface",
    "CacheItemPoolInterface",
    "CacheMixin",
    "Callback",
    "InvalidArgumentError",
    "ItemInterface",
    "Metadata",
    "NamespacedPoolInterface",
    "TagAwareCacheInterface",
    "__version__",
]
