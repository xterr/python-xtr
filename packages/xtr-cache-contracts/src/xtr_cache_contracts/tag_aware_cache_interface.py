"""A cache whose values can be invalidated in groups, by tag."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .cache_interface import CacheInterface

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["TagAwareCacheInterface"]


@runtime_checkable
class TagAwareCacheInterface(CacheInterface, Protocol):
    """A cache that can drop every value carrying a tag, without knowing their keys.

    A value is tagged when it is computed, through the item its callback
    receives:

    ```python
    async def load_invoice(item: ItemInterface) -> Invoice:
        item.tag(f"customer.{customer_id}")
        return await invoices.fetch(invoice_id)
    ```

    Invalidating ``customer.42`` later drops every invoice cached for that
    customer, whatever it was cached under.
    """

    async def invalidate_tags(self, tags: Iterable[str], /) -> bool:
        """Invalidate every value tagged with any of ``tags``.

        An implementation built on an item pool does not invalidate items
        saved as deferred and not yet committed; they are committed as usual.
        That lets a caller replace old tagged values with new ones without a
        window where neither is cached.

        Returns:
            ``False`` when the backend failed; ``True`` otherwise.

        Raises:
            InvalidArgumentError: When a tag is empty or holds a reserved
                character.
        """
        ...
