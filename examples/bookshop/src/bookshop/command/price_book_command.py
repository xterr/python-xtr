"""``catalog:price`` — arguments, a validator, and a qualified cache pool."""

from __future__ import annotations

from typing import Annotated

from xtr_cache_contracts import CacheInterface, ItemInterface
from xtr_console import Argument, ConsoleStyle, ExitCode, Range, as_command, escape
from xtr_dependency_injection import Injected, Target

from bookshop.service.book_catalog_interface import BookCatalogInterface
from bookshop.service.price_calculator import PriceCalculator

__all__ = ["price_book"]


@as_command("catalog:price")
async def price_book(  # noqa: PLR0913 — the command line plus three services.
    io: ConsoleStyle,
    isbn: str,
    quantity: Annotated[int, Argument(validator=Range(gte=1))] = 1,
    *,
    catalog: Injected[BookCatalogInterface],
    calculator: Injected[PriceCalculator],
    quotes: Annotated[CacheInterface, Target("quotes")],
) -> int:
    """Price a line through every pricing rule, in collection order — a quote is cached.

    The ``quotes`` pool keeps each quote five minutes (its ``default_lifetime``), in files
    under the kernel's share directory: run the command twice and the second answer says it
    came from the cache. ``bookshop cache:pool:clear quotes`` forgets them.

    Args:
        io: Where the command writes.
        isbn: The book (an argument).
        quantity: How many copies (an optional argument).
        catalog: The catalog, from the container.
        calculator: The pricing rules, from the container.
        quotes: The ``quotes`` cache pool, qualified.
    """
    book = catalog.find(isbn)
    if book is None:
        io.error(f"No book with ISBN {escape(isbn)}.")
        return ExitCode.FAILURE
    computed = False

    async def quote(item: ItemInterface) -> list[tuple[str, str]]:
        nonlocal computed
        computed = True
        del item
        return [(line.rule, str(line.amount)) for line in calculator.price(book, quantity)]

    lines = await quotes.get(f"price.{isbn}.{quantity}", quote)
    io.section(f"{escape(book.title)} x {quantity}")
    io.table(["Step", calculator.currency], [[rule, amount] for rule, amount in lines])
    io.text("Computed now." if computed else "From the quotes cache.")
    return ExitCode.SUCCESS
