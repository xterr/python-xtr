"""The routes: plain functions, their services injected per request.

A route takes the :class:`~bookshop.web.http.Request` as its first parameter — passed by the
server — and asks the container for the rest, exactly as a command or a handler does:
``Injected[T]``, ``Annotated[T, Autowire(param=... | env=...)]``. Bound with
``per_call_scope=True``, each call enters a scope of its own: a scoped service is built for
the request and released — its generator's cleanup run — when the request ends.
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, Final, final

from xtr_dependency_injection import Autowire, Injected, KernelInterface
from xtr_messenger import WorkerFactory

from bookshop.catalog import BookCatalogInterface, Genre
from bookshop.ordering import OrderBook, OrderNumber, OrderService, ShoppingCart, UnitOfWork
from bookshop.pricing import PriceCalculator
from fulltext import SearchEngineInterface

from .http import HttpError, Request, Response

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = ["ROUTES", "Route"]

_QUEUED = ("jobs", "audit", "outbox")


@final
@dataclass(frozen=True, slots=True)
class Route:
    """One route: a method, a path pattern with ``{name}`` segments, and what answers it."""

    method: str
    pattern: str
    endpoint: Callable[..., Awaitable[Response]]

    def match(self, method: str, path: str) -> dict[str, str] | None:
        """The captured segments when ``path`` fits the pattern (whatever the method)."""
        del method
        wanted = self.pattern.strip("/").split("/")
        given = path.strip("/").split("/")
        if len(wanted) != len(given):
            return None
        captured: dict[str, str] = {}
        for expected, actual in zip(wanted, given, strict=True):
            if expected.startswith("{") and expected.endswith("}"):
                captured[expected[1:-1]] = actual
            elif expected != actual:
                return None
        return captured


async def health(
    request: Request,
    kernel: Injected[KernelInterface],
    shop: Annotated[str, Autowire(param="shop.name")],
    tier: Annotated[str, Autowire(env="SHOP_TIER")],
) -> Response:
    """``GET /health`` — the kernel, a parameter holding ``env()``, a variable."""
    del request
    return Response.json(
        {"shop": shop, "tier": tier, "environment": kernel.environment, "debug": kernel.debug}
    )


async def list_books(
    request: Request,
    catalog: Injected[BookCatalogInterface],
    page_size: Annotated[int, Autowire(param="shop.page_size")],
) -> Response:
    """``GET /books?genre=software`` — the decorated catalog."""
    genre = request.query.get("genre")
    books = [b for b in catalog.all() if genre is None or b.genre is Genre(genre)]
    return Response.json([_book(b) for b in books[:page_size]])


async def show_book(
    request: Request,
    catalog: Injected[BookCatalogInterface],
    calculator: Injected[PriceCalculator],
) -> Response:
    """``GET /books/{isbn}?quantity=2`` — one book, priced through every rule."""
    book = catalog.find(request.path_params["isbn"])
    if book is None:
        raise HttpError(HTTPStatus.NOT_FOUND, f"no book {request.path_params['isbn']}")
    quantity = int(request.query.get("quantity", "1"))
    lines = calculator.price(book, quantity)
    return Response.json({**_book(book), "pricing": [[line.rule, line.amount] for line in lines]})


async def search(request: Request, engine: Injected[SearchEngineInterface]) -> Response:
    """``GET /search?q=...`` — the library's engine, decorated by its own bundle."""
    query = request.query.get("q", "")
    return Response.json([{"isbn": hit.key, "score": hit.score} for hit in engine.search(query)])


async def list_orders(request: Request, orders: Injected[OrderBook]) -> Response:
    """``GET /orders`` — the singleton order book: it outlives every request."""
    del request
    return Response.json(
        [
            {"number": o.number, "isbn": o.isbn, "quantity": o.quantity, "total": o.total}
            for o in orders.all()
        ]
    )


async def place_order(  # noqa: PLR0913, PLR0917 — the request plus one service per concern.
    request: Request,
    cart: Injected[ShoppingCart],
    work: Injected[UnitOfWork],
    number: Injected[OrderNumber],
    orders: Injected[OrderService],
    workers: Injected[WorkerFactory],
) -> Response:
    """``POST /orders {"isbn", "quantity", "email"}`` — scoped cart and unit of work.

    The cart and the unit of work are this request's; the unit of work commits when the
    request's scope closes, after this returns. The worker then drains what was queued.
    """
    payload = request.json()
    cart.add(str(payload.get("isbn", "")), int(str(payload.get("quantity", 1))))
    envelopes = await orders.place(cart, str(payload.get("email", "")), number, work)
    for name in _QUEUED:
        await workers.worker([name]).run()
    return Response.json(
        {"number": number.value, "unit_of_work": work.id, "dispatched": len(envelopes)},
        HTTPStatus.CREATED,
    )


def _book(book: object) -> dict[str, object]:
    return {name: getattr(book, name) for name in ("isbn", "title", "author", "price", "genre")}


ROUTES: Final = (
    Route("GET", "/health", health),
    Route("GET", "/books", list_books),
    Route("GET", "/books/{isbn}", show_book),
    Route("GET", "/search", search),
    Route("GET", "/orders", list_orders),
    Route("POST", "/orders", place_order),
)
