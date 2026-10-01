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

import anyio
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from xtr_dependency_injection import Autowire, Injected, KernelInterface, Target
from xtr_http_kernel.rate_limiter import RateLimited
from xtr_messenger import WorkerFactory
from xtr_password_hasher import UserPasswordHasherInterface
from xtr_rate_limiter import RateLimiterFactoryInterface
from xtr_security import Security
from xtr_security_core import InMemoryUser, InMemoryUserProvider
from xtr_security_core.exception import (
    AuthenticationCredentialsNotFoundError,
    UserNotFoundError,
)
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser, Firewall, IsGranted
from xtr_security_jwt import JwtTokenManagerInterface

from bookshop.catalog import Book, BookCatalogInterface, Genre
from bookshop.ordering import (
    ORDER_VIEW,
    Order,
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

# A hash of a throwaway password, verified against when no such user exists, so a bad
# identifier and a bad password cost the same (the FastAPI-tutorial timing guard). A PHC hash
# string is one indivisible token, so it cannot be wrapped under the line length.
_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$csBCmuUDDdOHBAwK4xX+lA$0YF1rPunzp1YVD+n8Nv5+KjL0faOrgKXKbXhOVSOXxE"  # noqa: E501

# Limited before its routes are added, then guarded by the matched firewall: each route copies
# the router's dependencies, so every route authenticates once and is checked against the
# access-control map of config/security.py.
router = Firewall()(RateLimited("api", expose_headers=True)(APIRouter()))


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


class TokenRequest(BaseModel):
    """The body ``POST /token`` takes, an identifier and the password to verify.

    Attributes:
        identifier: Who is signing in — one of the inline users of ``config/security.py``.
        password: Their plaintext password, checked against the stored argon2id hash.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    identifier: str
    password: str


@router.post("/token", dependencies=[RateLimited("orders_per_email")])
async def issue_token(
    body: TokenRequest,
    users: Annotated[InMemoryUserProvider, Target("users")],
    hasher: Injected[UserPasswordHasherInterface],
    tokens: Injected[JwtTokenManagerInterface],
) -> dict[str, str]:
    """``POST /token {"identifier", "password"}`` — a signed token after the password checks.

    The application authenticates the user itself, the FastAPI-tutorial way: load the user,
    verify the password off the event loop, and — for an unknown identifier — burn a dummy
    hash so a bad identifier and a bad password take the same time. The token manager signs
    the user's identity and roles; it reads nothing from client input. Throttled per
    identifier with the ``orders_per_email`` limiter, so a password cannot be guessed at speed.

    Raises:
        AuthenticationCredentialsNotFoundError: If the identifier or password is wrong;
            answered as 401.
    """
    user: InMemoryUser | None = None
    try:
        loaded = await users.load_user_by_identifier(body.identifier)
    except UserNotFoundError:
        loaded = None
    if isinstance(loaded, InMemoryUser):
        user = loaded
    probe = user if user is not None else InMemoryUser("__unknown__", password=_DUMMY_HASH)
    valid = await anyio.to_thread.run_sync(hasher.is_password_valid, probe, body.password)
    if user is None or not valid:
        raise AuthenticationCredentialsNotFoundError("Bad credentials.")
    return {"access_token": await tokens.create(user), "token_type": "bearer"}


@router.get("/me")
async def me(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, object]:
    """``GET /me`` — the authenticated user behind the request, from the firewall's token."""
    return {"identifier": user.get_user_identifier(), "roles": list(user.get_roles())}


async def _load_order(number: str, orders: Injected[OrderRepository]) -> Order:
    """Load the order ``number`` names, for the endpoint and the ``ORDER_VIEW`` check to share.

    Raises:
        UnknownBookError: Reused to answer 404 when no order carries ``number``.
    """
    order = await orders.get_one_or_none(number=number)
    if order is None:
        raise UnknownBookError(number)
    return order


@router.get("/orders/{number}")
async def show_order(
    order: Annotated[Order, Depends(_load_order)],
    security: Injected[Security],
) -> dict[str, object]:
    """``GET /orders/{number}`` — one order, only to the customer who placed it.

    The ``ORDER_VIEW`` attribute is checked over the loaded order with the ``Security`` facade's
    ``deny_access_unless_granted`` — the plan's in-body form — so the ``OrderViewVoter`` votes on
    the real :class:`Order`: the owner, or an admin through the role hierarchy, is granted;
    anyone else raises ``AccessDeniedError``, which the firewall answers 403.
    """
    await security.deny_access_unless_granted(ORDER_VIEW, order)
    return {
        "number": order.number,
        "isbn": order.isbn,
        "quantity": order.quantity,
        "email": order.email,
        "total": order.total,
    }


@router.get("/admin/stats")
@IsGranted("ROLE_ADMIN")
async def admin_stats(orders: Injected[OrderRepository]) -> dict[str, object]:
    """``GET /admin/stats`` — the order count, for an admin only.

    ``@IsGranted("ROLE_ADMIN")`` below the route (the access map also guards ``^/admin``)
    answers 403 for a signed-in non-admin, 401 for an anonymous caller.
    """
    return {"orders": await orders.count()}


def _book(book: Book) -> dict[str, object]:
    return {
        "isbn": book.isbn,
        "title": book.title,
        "author": book.author,
        "price": book.price,
        "genre": book.genre,
    }
