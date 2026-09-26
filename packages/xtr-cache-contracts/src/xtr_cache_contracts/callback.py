"""What computes a value a cache does not have yet."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias, TypeVar

from .item_interface import ItemInterface

__all__ = ["Callback"]

_T = TypeVar("_T")

Callback: TypeAlias = Callable[[ItemInterface], Awaitable[_T]]
"""Computes the value for an item, on a miss.

Receives the item the value is for, so it can set how long the value lives
(:meth:`~xtr_cache_contracts.item_interface.ItemInterface.expires_after`) or
tag it (:meth:`~xtr_cache_contracts.item_interface.ItemInterface.tag`), and
returns the value. Asynchronous, because computing a value worth caching is
usually I/O.

Any ``async def`` taking the item fits, and so does an object with an
``async def __call__`` taking it. Raising stores nothing: the error reaches
the caller of :meth:`~xtr_cache_contracts.cache_interface.CacheInterface.get`
as it was raised.

```python
async def load_profile(item: ItemInterface) -> Profile:
    item.expires_after(3600)
    return await profiles.fetch(user_id)
```
"""
