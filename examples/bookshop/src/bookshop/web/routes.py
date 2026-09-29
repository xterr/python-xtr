"""The routes: one router of plain functions, their services injected per request.

An endpoint is written the way the framework documents it — path and query parameters in the
signature, a model for the body — and asks the container for the rest with the markers a
command or a handler already uses: ``Injected[T]``, ``Annotated[T, Autowire(param=... |
env=...)]``. Each marker stands for one framework dependency, so the injected services stay out
of the documented parameters while the framework fills the rest of the signature as it always
does.

Every request runs in a scope of its own, opened by ``setup`` in :mod:`bookshop.web.app`: the
cart and the unit of work are built for the request and released once the response has gone
out — which is when the unit of work commits.

Rate limits, each a limiter of ``config/rate_limiter.py`` — every way to declare one:

- the router — every route, per client (``api``), with ``X-RateLimit-*`` headers;
- a decorator below the route — ``GET /search`` (``search``);
- the route's ``dependencies`` — ``POST /orders`` (``ordering``, a compound limit);
- a limiter injected by name and consumed by hand — ``POST /orders``, per email address
  (``orders_per_email``), since the address is in the body, which no dependency reads.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, ClassVar

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from xtr_dependency_injection import Autowire, Injected, KernelInterface, Target
from xtr_http_kernel.rate_limiter import RateLimited
from xtr_messenger import WorkerFactory
from xtr_rate_limiter import RateLimiterFactoryInterface

from bookshop.catalog import Book, BookCatalogInterface, Genre
from bookshop.ordering import (
    OrderNumber,
    OrderRepository,
    OrderService,
    ShoppingCart,
    UnitOfWork,
)
from bookshop.ordering.errors import UnknownBookError
from bookshop.pricing import PriceCalculator
from fulltext import SearchEngineInterface

__all__ = ["OrderRequest", "router"]

_QUEUED = ("jobs", "audit", "outbox")

# Limited before its routes are added: each route copies the router's dependencies.
router = RateLimited("api", expose_headers=True)(APIRouter())


class OrderRequest(BaseModel):
    """The body ``POST /orders`` takes, validated before the endpoint runs.

    Attributes:
        isbn: The book to order.
        quantity: How many copies.
        email: Who is ordering.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    isbn: str
    quantity: Annotated[int, Field(ge=1)] = 1
    email: str


@router.get("/health")
async def health(
    kernel: Injected[KernelInterface],
    shop: Annotated[str, Autowire(param="shop.name")],
    tier: Annotated[str, Autowire(env="SHOP_TIER")],
) -> dict[str, object]:
    """``GET /health`` — the kernel, a parameter holding ``env()``, a variable."""
    return {"shop": shop, "tier": tier, "environment": kernel.environment, "debug": kernel.debug}


@router.get("/books")
async def list_books(
    catalog: Injected[BookCatalogInterface],
    page_size: Annotated[int, Autowire(param="shop.page_size")],
    genre: Genre | None = None,
) -> list[dict[str, object]]:
    """``GET /books?genre=software`` — the decorated catalog."""
    books = [book for book in catalog.all() if genre is None or book.genre is genre]
    return [_book(book) for book in books[:page_size]]


@router.get("/books/{isbn}")
async def show_book(
    isbn: str,
    catalog: Injected[BookCatalogInterface],
    calculator: Injected[PriceCalculator],
    quantity: int = 1,
) -> dict[str, object]:
    """``GET /books/{isbn}?quantity=2`` — one book, priced through every rule.

    Raises:
        UnknownBookError: If the catalog holds no such ISBN; answered as 404.
    """
    book = catalog.find(isbn)
    if book is None:
        raise UnknownBookError(isbn)
    lines = calculator.price(book, quantity)
    return {**_book(book), "pricing": [[line.rule, line.amount] for line in lines]}


@router.get("/search")
@RateLimited("search", expose_headers=True)  # below the route: the route reads what it wraps
async def search(engine: Injected[SearchEngineInterface], q: str = "") -> list[dict[str, object]]:
    """``GET /search?q=...`` — the library's engine, decorated by its own bundle.

    Five a minute per client: the sixth is answered 429, with ``Retry-After``.
    """
    return [{"isbn": hit.key, "score": hit.score} for hit in engine.search(q)]


@router.get("/orders")
async def list_orders(orders: Injected[OrderRepository]) -> list[dict[str, object]]:
    """``GET /orders`` — read from the database, through this request's repository."""
    return [
        {"number": o.number, "isbn": o.isbn, "quantity": o.quantity, "total": o.total}
        for o in await orders.list(order_by=[("created_at", True)])
    ]


@router.post("/orders", status_code=HTTPStatus.CREATED, dependencies=[RateLimited("ordering")])
async def place_order(  # noqa: PLR0913, PLR0917 — the body plus one service per concern.
    order: OrderRequest,
    per_email: Annotated[RateLimiterFactoryInterface, Target("orders_per_email")],
    cart: Injected[ShoppingCart],
    work: Injected[UnitOfWork],
    number: Injected[OrderNumber],
    orders: Injected[OrderService],
    workers: Injected[WorkerFactory],
) -> dict[str, object]:
    """``POST /orders {"isbn", "quantity", "email"}`` — scoped cart and unit of work.

    The cart and the unit of work are this request's; the unit of work commits when the
    request's scope closes, after the response has gone out. The worker drains what was
    queued before that.

    Raises:
        RateLimitExceededError: If the address placed two orders this hour already;
            answered as 429.
        UnknownBookError: If the ISBN names no book; answered as 404.
        OrderRefusedError: If the fraud check refuses the order; answered as 422.
    """
    _ = (await per_email.create(order.email.lower()).consume()).ensure_accepted()
    cart.add(order.isbn, order.quantity)
    envelopes = await orders.place(cart, order.email, number, work)
    for name in _QUEUED:
        await workers.worker([name]).run()
    return {"number": number.value, "unit_of_work": work.id, "dispatched": len(envelopes)}


def _book(book: Book) -> dict[str, object]:
    return {
        "isbn": book.isbn,
        "title": book.title,
        "author": book.author,
        "price": book.price,
        "genre": book.genre,
    }
