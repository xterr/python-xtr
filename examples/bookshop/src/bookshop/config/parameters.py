"""The application's parameters: named values injected with ``Autowire(param="...")``.

Parameters from the kernel (``kernel.*``), from bundles (``builder.set_parameter``) and from
``@parameters`` functions merge into one nested mapping. They never override: a leaf set
twice is a ``ParameterConflictError`` naming both sources. A key never contains a dot —
nesting is what makes ``shop.var_dir`` a path.

Strings may reference other parameters and the environment:

==================================  =============================================
Written                             Becomes
==================================  =============================================
``"%kernel.project_dir%"``          the parameter itself, whatever its type
``"%kernel.project_dir%/var"``      the parameter embedded in the string
``"100%%"``                         ``100%`` — an escaped percent sign
``"%env(int:SHOP_PAGE_SIZE)%"``     the placeholder ``env("int:SHOP_PAGE_SIZE")``
``env("SHOP_NAME")``                the same placeholder, spelled in Python
==================================  =============================================

A placeholder is resolved when a service needing it is built, never while the kernel builds.
"""

from __future__ import annotations

from decimal import Decimal

from xtr_dependency_injection import env, parameters

from bookshop.env.tier import Tier

__all__ = ["shop_parameters"]

_SUPPORT = "support@bookshop.example"


@parameters
def shop_parameters() -> dict[str, object]:
    """Return the ``shop.*`` parameters. Takes no arguments; returns a mapping.

    ``env()`` spellings, all placeholders read when injected:

    - ``env("X")`` — a string;
    - ``env("X", default=...)`` — the default when ``X`` is unset;
    - ``env("X", Tier)`` — an ``Enum`` class becomes the ``enum:`` prefix;
    - ``env("X", Decimal, default=...)`` — any other callable is applied to the value;
    - ``f"...{env('X')}..."`` — a placeholder embedded in a string stays one.
    """
    return {
        "shop": {
            "name": env("SHOP_NAME"),
            "currency": "EUR",
            "vat_rate": 0.09,
            "tier": env("SHOP_TIER", Tier),
            "free_shipping_over": env("SHOP_FREE_SHIPPING_OVER", Decimal, default=Decimal(50)),
            "var_dir": "%kernel.project_dir%/var",
            # A parameter referencing another application parameter.
            "log_dir": "%shop.var_dir%/log",
            "secrets_dir": "%kernel.project_dir%/secrets",
            "page_size": "%env(int:SHOP_PAGE_SIZE)%",
            "support_email": env("SHOP_SUPPORT_EMAIL", default=_SUPPORT),
            "support_link": f"mailto:{env('SHOP_SUPPORT_EMAIL', default=_SUPPORT)}?subject=Order",
            "motto": "100%% independent",
            # Read by the ``default:shop.fallback_name:SHOP_NICKNAME`` env expression.
            "fallback_name": "The Corner Bookshop",
            "features": {"search": True, "web": True, "payments": False},
        },
    }
