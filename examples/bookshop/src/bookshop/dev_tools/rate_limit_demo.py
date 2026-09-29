"""``demo:rate-limit`` — every limiter of ``config/rate_limiter.py`` and every limited route.

Each row is a claim the README makes, checked as it runs: the command exits 1 if one does not
hold, so it is the executable proof of the rate limits.

- **The limiters**, on a test kernel of their own (``boot_for_test``: nothing kept between
  runs), under a frozen clock (``mock_time``) — so "a minute later" takes no time, and a
  reservation's wait moves the clock rather than the command.
- **The web application**, served in process the way a server would — every way a route can
  be limited, the ``X-RateLimit-*`` headers, and the shop's own 429 bodies. Each run limits a
  fresh address; the one per-client count it relies on is ``reset()`` first, the way an
  operator clears a limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Final, cast, final
from uuid import uuid4

import httpx
from xtr_clock import MockClock
from xtr_clock.testing import mock_time
from xtr_console import ConsoleStyle, ExitCode, as_command
from xtr_dependency_injection import Injected
from xtr_dependency_injection.testing import boot_for_test
from xtr_rate_limiter import (
    MaxWaitDurationExceededError,
    RateLimiterBuilder,
    RateLimiterFactoryInterface,
    RateLimitExceededError,
)
from xtr_service_contracts import ContainerInterface

from bookshop.kernel import kernel

__all__ = ["rate_limit"]

_FROZEN_AT: Final = "2026-03-10 12:00:00"
_CLIENT: Final = "127.0.0.1"
_ISBN: Final = "978-0141439518"
_OTHER_ISBN: Final = "978-0135957059"
_SEARCHES: Final = 5
_ORDER_BURST: Final = 3
_ORDER_REFILL: Final = 20
_ORDERS_PER_EMAIL: Final = 2
_MAX_WAIT: Final = 5.0
_HEADERS: Final = ["Claim", "Result", "Observed"]

_OK: Final = HTTPStatus.OK
_NOT_FOUND: Final = HTTPStatus.NOT_FOUND
_TOO_MANY: Final = HTTPStatus.TOO_MANY_REQUESTS


@final
@dataclass
class _Checks:
    """The claims checked so far, and whether each held."""

    rows: list[list[str]] = field(default_factory=list)
    failed: int = 0

    def check(self, claim: str, held: bool, observed: str = "") -> None:
        """Record ``claim``, with what was observed."""
        self.rows.append([claim, "ok" if held else "FAILED", observed])
        self.failed += 0 if held else 1


@as_command("demo:rate-limit")
async def rate_limit(io: ConsoleStyle, container: Injected[ContainerInterface]) -> int:
    """Check every limiter, and every rate-limited route, against what the README says.

    Args:
        io: Where the command writes.
        container: This kernel's container, to reset the per-client count the web part uses.
    """
    checks = _Checks()
    io.title("Rate limits")

    io.section("The limiters — a test kernel, a frozen clock")
    async with await boot_for_test(kernel) as booted:
        with mock_time(_FROZEN_AT) as clock:
            limiters = booted.container
            await _fixed_window(limiters, clock, checks)
            await _sliding_window(limiters, clock, checks)
            await _token_bucket(limiters, clock, checks)
            await _calendar_and_compound(limiters, checks)
            await _outside_the_web(limiters, clock, checks)
    io.table(_HEADERS, checks.rows)

    io.section("The web application — served in process")
    first = len(checks.rows)
    await _reset_web_counts(container)
    await _web(checks)
    io.table(_HEADERS, checks.rows[first:])

    if checks.failed:
        io.error(f"{checks.failed} claim(s) did not hold.")
        return ExitCode.FAILURE
    io.success(f"All {len(checks.rows)} claims held.")
    return ExitCode.SUCCESS


async def _limiter(container: ContainerInterface, name: str) -> RateLimiterFactoryInterface:
    return await container.get(RateLimiterFactoryInterface, name)


async def _fixed_window(container: ContainerInterface, clock: MockClock, checks: _Checks) -> None:
    """``search``: five a minute, counted in this process."""
    search = (await _limiter(container, "search")).create("alice")
    start = clock.now().timestamp()
    accepted = [(await search.consume()).is_accepted() for _ in range(_SEARCHES)]
    refused = await search.consume()
    checks.check(
        "search: five a minute, the sixth refused",
        all(accepted) and not refused.is_accepted(),
        f"retry after {refused.retry_after:%H:%M:%S}",
    )
    checks.check(
        "search: retry when the window ends", refused.retry_after.timestamp() == start + 60
    )
    clock.sleep(61)
    checks.check("search: a new window accepts again", (await search.consume()).is_accepted())
    await search.reset()
    full = (await search.consume(0)).remaining_tokens
    checks.check("search: reset forgets every hit", full == _SEARCHES, f"{full} left")


async def _sliding_window(container: ContainerInterface, clock: MockClock, checks: _Checks) -> None:
    """``api``: 120 a minute, the last window fading out as the current one passes."""
    api = (await _limiter(container, "api")).create("alice")
    burst = await api.consume(120)
    over = await api.consume()
    clock.sleep(90)
    half = await api.consume(60)
    beyond = await api.consume()
    checks.check(
        "api: 120 a minute, sliding",
        burst.is_accepted() and not over.is_accepted(),
        f"{burst.remaining_tokens} left after 120",
    )
    checks.check(
        "api: half a window later, half the last one still counts",
        half.is_accepted() and not beyond.is_accepted(),
    )


async def _token_bucket(container: ContainerInterface, clock: MockClock, checks: _Checks) -> None:
    """``orders``: a burst of three, then one every twenty seconds; reserving and waiting."""
    orders = (await _limiter(container, "orders")).create("bob")
    bursts = [(await orders.consume()).is_accepted() for _ in range(3)]
    empty = await orders.consume()
    before = clock.now().timestamp()
    reservation = await orders.reserve()
    await reservation.wait()
    waited = clock.now().timestamp() - before
    checks.check(
        "orders: a burst of three, the fourth refused",
        all(bursts) and not empty.is_accepted(),
        f"retry in {empty.retry_after.timestamp() - before:.0f}s",
    )
    checks.check(
        "orders: a reservation waits for the next token",
        waited == _ORDER_REFILL,
        f"waited {waited:.0f}s",
    )
    checks.check(
        "orders: the reserved token went to the one who booked it",
        not (await orders.consume()).is_accepted(),
    )
    try:
        _ = await orders.reserve(max_time=_MAX_WAIT)
        waited_too_long = False
    except MaxWaitDurationExceededError as error:
        waited_too_long = error.wait_duration > _MAX_WAIT
    checks.check("orders: a wait past max_time books nothing and raises", waited_too_long)


async def _calendar_and_compound(container: ContainerInterface, checks: _Checks) -> None:
    """``orders_monthly`` follows the calendar; ``ordering`` applies both limits at once."""
    monthly = await (await _limiter(container, "orders_monthly")).create("shop").consume()
    reset_at = f"{monthly.reset_at:%Y-%m-%d %H:%M}" if monthly.reset_at else "never"
    checks.check(
        "orders_monthly: full again on the first of next month",
        reset_at == "2026-04-01 00:00",
        f"reset at {reset_at}",
    )

    ordering = (await _limiter(container, "ordering")).create("carol")
    combined = [await ordering.consume() for _ in range(4)]
    checks.check(
        "ordering: every limit applies, the tightest answers",
        [limit.is_accepted() for limit in combined] == [True, True, True, False]
        and combined[0].remaining_tokens == _ORDER_BURST - 1,
        f"{combined[0].remaining_tokens} left after one, refused by a limit of {combined[3].limit}",
    )


async def _outside_the_web(
    container: ContainerInterface, clock: MockClock, checks: _Checks
) -> None:
    """What ``POST /orders`` and ``send_receipt`` do by hand, and the builder."""
    per_email = (await _limiter(container, "orders_per_email")).create("dave@example.com")
    _ = [await per_email.consume() for _ in range(_ORDERS_PER_EMAIL)]
    try:
        _ = (await per_email.consume()).ensure_accepted()
        raised = False
    except RateLimitExceededError:
        raised = True
    checks.check("orders_per_email: the third order this hour raises", raised)

    mail = (await _limiter(container, "outbound_mail")).create("provider")
    turns = [await mail.reserve() for _ in range(12)]
    waits = [round(turn.time_to_act - clock.now().timestamp()) for turn in turns[9:]]
    checks.check(
        "outbound_mail: ten at once, then one every six seconds",
        waits == [0, 6, 12],
        f"the 10th, 11th, 12th wait {waits}",
    )

    builder = await container.get(RateLimiterBuilder)
    tenant = builder.token_bucket("tenant-7", 2, "1 second").create("erin")
    decided = [(await tenant.consume()).is_accepted() for _ in range(3)]
    checks.check("builder: a limit built in code", decided == [True, True, False])


async def _reset_web_counts(container: ContainerInterface) -> None:
    """Start the web part from full counts: what an operator's reset looks like."""
    api = await _limiter(container, "api")
    for route in ("GET~/search", "GET~/books/{isbn}", "POST~/orders"):
        await api.create(f"{_CLIENT}~{route}").reset()
    orders = await _limiter(container, "orders")
    await orders.create(f"{_CLIENT}~POST~/orders").reset()


async def _web(checks: _Checks) -> None:
    # Imported here: importing it builds the application, which serves from its own kernel.
    from bookshop.web.app import app  # noqa: PLC0415

    email = f"reader-{uuid4().hex[:8]}@example.com"
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, client=(_CLIENT, 51234))
        async with httpx.AsyncClient(transport=transport, base_url="http://bookshop") as client:
            searches = [await client.get("/search", params={"q": "pride"}) for _ in range(6)]
            books = [await client.get(f"/books/{isbn}") for isbn in (_ISBN, _OTHER_ISBN)]
            body = {"isbn": "nope", "quantity": 1, "email": email}
            posted = [await client.post("/orders", json=body) for _ in range(3)]
            fourth = await client.post("/orders", json={**body, "email": f"x-{email}"})

    statuses = [response.status_code for response in searches]
    refusal = searches[-1]
    checks.check(
        "GET /search: the decorator's limit, five a minute",
        statuses == [_OK] * _SEARCHES + [_TOO_MANY],
        " ".join(map(str, statuses)),
    )
    headers = [
        _header(searches[0], "x-ratelimit-limit"),
        _header(searches[4], "x-ratelimit-remaining"),
    ]
    checks.check(
        "GET /search: the closest limit speaks in the headers",
        headers == [str(_SEARCHES), "0"],
        f"limit {headers[0]}, then {headers[1]} left",
    )
    checks.check(
        "GET /search: 429 in the shop's shape, with Retry-After",
        _json(refusal).get("limiter") == "search" and "retry-after" in refusal.headers,
        f"{_json(refusal)}",
    )
    remaining = [int(_header(book, "x-ratelimit-remaining") or "-1") for book in books]
    checks.check(
        "GET /books/{isbn}: the router's limit, one count for every book",
        _header(books[0], "x-ratelimit-limit") == "120" and remaining[1] == remaining[0] - 1,
        f"remaining {remaining[0]} then {remaining[1]}",
    )
    checks.check(
        "every counted response is private", _header(books[0], "cache-control") == "private"
    )
    checks.check(
        "POST /orders: an injected limiter, two orders an hour per address",
        [response.status_code for response in posted] == [_NOT_FOUND, _NOT_FOUND, _TOO_MANY]
        and _json(posted[-1]).get("error") == "too many orders from this address",
        " ".join(str(response.status_code) for response in posted),
    )
    checks.check(
        "POST /orders: the route's compound limit, three in a burst",
        fourth.status_code == _TOO_MANY and _json(fourth).get("limiter") == "ordering",
        f"{_json(fourth)}",
    )


def _header(response: httpx.Response, name: str) -> str | None:
    """Read one response header; ``None`` when the response has none."""
    value: str | None = response.headers.get(name)  # pyright: ignore[reportAny] -- the client types its headers loosely
    return value


def _json(response: httpx.Response) -> dict[str, object]:
    """Read a response's JSON body, which every route of the shop answers with an object."""
    return cast("dict[str, object]", response.json())
