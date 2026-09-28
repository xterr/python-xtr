"""The application itself: the routes, the errors it answers with, and the kernel behind it.

Built the way the framework documents it — a router included, one exception handler per domain
error the application gives a status of its own — and then one call, ``setup(app, kernel)``,
which is the whole of serving it from the kernel: every application life builds and boots its
own kernel and shuts it down again with the lifespan, and every request runs inside the scope
its scoped services live in, through the lifecycle the ``http_kernel`` bundle contributed.

Left out of the container's scan (``EXCLUDE`` in :mod:`bookshop.kernel`): importing this module
builds the application the kernel itself serves.
"""

from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from xtr_http_kernel import setup

from bookshop.kernel import kernel
from bookshop.ordering.errors import OrderRefusedError, UnknownBookError

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


setup(app, kernel)
