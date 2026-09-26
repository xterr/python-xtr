"""The application's configuration: one module per bundle, plus the parameters.

Configuration is Python. Each ``@configure`` function either *provides* a bundle's config
(no argument — a base) or *transforms* it (one argument, the current value); its return
annotation says which bundle it configures. Per bundle, the config resolves in this order,
every step recorded — run ``bookshop debug:config``:

1. the bundle's default, ``Config()``;
2. the application's base — a ``@when``/``@when_not`` one wins over an unconditional one;
3. an ``AliasOf`` forward from another bundle's config;
4. other bundles' ``prepend_extension``, in bundle order;
5. the application's transforms — unconditional, then conditional; by ``priority``, then
   scan order.
"""

from __future__ import annotations

__all__: list[str] = []
