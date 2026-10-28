"""The rate limiters: one per thing the shop limits, each with the policy that suits it.

Every limiter is a ``RateLimiterFactoryInterface`` qualified by its name. The web routes name
theirs in ``RateLimited(...)`` (``web/routes.py``); a handler and a route ask for one with
``Target(...)`` (``messaging/handlers.py``, ``web/routes.py``). ``demo:rate-limit`` runs every
one of them.

Where the state lives:

- the default — the ``rate_limiter`` cache pool the bundle adds, on the app pool's adapter
  (files in dev, memory in tests), each change under the lock bundle's ``default`` lock, so
  every process on the machine shares the count;
- ``"in-memory"`` — this process only, for a count nobody else needs to see;
- ``SHOP_RATE_LIMIT_STORAGE`` — ``cache`` unless set; ``.env.prod`` sets a Redis DSN, where
  the orders are counted atomically on the server, with no lock.
"""

from __future__ import annotations

from xtr_dependency_injection import configure, env
from xtr_rate_limiter import LimiterConfig, Rate
from xtr_rate_limiter.bundle import RateLimiterConfig

__all__ = ["rate_limiter"]


@configure
def rate_limiter() -> RateLimiterConfig:
    """Every limit the shop applies, by name."""
    return RateLimiterConfig(
        limiters={
            # Every route, per client: a sliding window, so a burst at a window's edge
            # still counts against the next one.
            "api": LimiterConfig("sliding_window", limit=120, interval="1 minute"),
            # Search is the expensive route: five a minute per client, counted in this
            # process only.
            "search": LimiterConfig(
                "fixed_window", limit=5, interval="1 minute", storage="in-memory", lock=None
            ),
            # Placing orders: a burst of three, then one every twenty seconds.
            "orders": LimiterConfig(
                "token_bucket",
                limit=3,
                rate=Rate("20 seconds"),
                storage=env("SHOP_RATE_LIMIT_STORAGE", default="cache"),
            ),
            # The whole shop takes at most a thousand orders per calendar month.
            "orders_monthly": LimiterConfig(
                "fixed_window",
                limit=1000,
                interval="1 month",
                anchor_at="2026-01-01T00:00:00+00:00",
            ),
            # Both at once: the monthly cap is one count for the shop, not one per client.
            "ordering": LimiterConfig(
                "compound",
                limiters=["orders", "orders_monthly"],
                keys={"orders_monthly": "shop"},
            ),
            # At most two orders an hour per address — checked by hand in POST /orders.
            "orders_per_email": LimiterConfig("fixed_window", limit=2, interval="1 hour"),
            # The mail provider takes ten a minute: receipts wait their turn.
            "outbound_mail": LimiterConfig("token_bucket", limit=10, rate=Rate("6 seconds")),
        },
    )
