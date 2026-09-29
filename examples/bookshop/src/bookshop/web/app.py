"""The application itself: the routes, the errors it answers with, and the kernel behind it.

Built the way the framework documents it — a router included, one exception handler per domain
error the application gives a status of its own, a refused rate limit among them — and then one
call, ``setup(app, kernel)``,
which is the whole of serving it from the kernel: every application life builds and boots its
own kernel and shuts it down again with the lifespan, and every request runs inside the scope
its scoped services live in, through the lifecycle the ``http_kernel`` bundle contributed.

Left out of the container's scan (``EXCLUDE`` in :mod:`bookshop.kernel`): importing this module
builds the application the kernel itself serves.
"""

from __future__ import annotations

import math
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from xtr_clock import Clock
from xtr_http_kernel import setup
from xtr_http_kernel.exception import TooManyRequestsError
from xtr_messenger import HandlersFailedError
from xtr_rate_limiter import RateLimitExceededError

from bookshop.kernel import kernel
from bookshop.ordering.errors import OrderError, OrderRefusedError, UnknownBookError

from .routes import router

__all__ = ["app"]

app = FastAPI(title="bookshop")
app.include_router(router)


@app.exception_handler(UnknownBookError)
async def unknown_book(request: Request, exc: UnknownBookError) -> JSONResponse:
    """Answer 404: the ISBN names nothing the catalog holds."""
    del request
    return JSONResponse({"error": str(exc)}, status_code=HTTPStatus.NOT_FOUND)


@app.exception_handler(OrderRefusedError)
async def order_refused(request: Request, exc: OrderRefusedError) -> JSONResponse:
    """Answer 422: the order was well-formed and the fraud check refused it."""
    del request
    return JSONResponse({"error": str(exc)}, status_code=HTTPStatus.UNPROCESSABLE_ENTITY)


@app.exception_handler(HandlersFailedError)
async def order_rolled_back(request: Request, exc: HandlersFailedError) -> JSONResponse:
    """Answer 409: a handler refused the order, and what the message wrote was rolled back.

    Only a refusal — an ``OrderError`` from every failed handler — is the client's to hear
    about; anything else is a fault, raised on to become a 500.
    """
    del request
    if not all(isinstance(error, OrderError) for error in exc.errors.values()):
        raise exc
    refused = {name: str(error) for name, error in exc.errors.items()}
    return JSONResponse(
        {"error": "rolled back", "handlers": refused}, status_code=HTTPStatus.CONFLICT
    )


@app.exception_handler(TooManyRequestsError)
async def too_many_requests(request: Request, exc: TooManyRequestsError) -> JSONResponse:
    """Answer a route's rate limit in the shop's own shape; ``Retry-After`` stays.

    Without this handler the framework answers ``{"detail": "Too Many Requests"}``.
    """
    del request
    return JSONResponse(
        {"error": "too many requests", "limiter": exc.limiter, "retry_after": exc.retry_after},
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(RateLimitExceededError)
async def too_many_orders(request: Request, exc: RateLimitExceededError) -> JSONResponse:
    """Answer 429: this address placed its two orders this hour (``ensure_accepted``)."""
    del request
    retry_after = max(0, math.ceil(exc.retry_after.timestamp() - Clock().now().timestamp()))
    return JSONResponse(
        {"error": "too many orders from this address", "retry_after": retry_after},
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
        headers={"Retry-After": str(retry_after)},
    )


setup(app, kernel)
