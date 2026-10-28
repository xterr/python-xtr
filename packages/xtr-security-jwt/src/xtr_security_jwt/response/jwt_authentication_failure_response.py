"""The response a failed token authentication answers a request with."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface
    from xtr_http_message_contracts.factory import ResponseFactoryInterface

__all__ = ["jwt_authentication_failure_response"]


async def jwt_authentication_failure_response(
    responses: ResponseFactoryInterface,
    message: str = "Bad credentials",
    status_code: int = 401,
) -> ResponseInterface:
    """Return a ``status_code`` JSON response naming why a token was refused.

    Built through ``responses``, so this names no response class. The body is
    ``{"code": <status>, "message": <message>}`` and it always carries a
    ``WWW-Authenticate: Bearer`` header, so a client is told both what went
    wrong and how to authenticate. It forbids every cache from keeping the
    refusal — ``Cache-Control: no-store`` and, for the caches that read only
    it, ``Pragma: no-cache`` — so a proxy cannot answer another caller's
    request with one principal's refusal. A listener may swap the response for
    one of its own on the matching failure event.

    Args:
        responses: Builds the response, so the caller names no class.
        message: The reason the token was refused.
        status_code: The status code to answer with.
    """
    response = responses.create_response(status_code)
    for name, value in {
        "www-authenticate": "Bearer",
        "cache-control": "no-store",
        "pragma": "no-cache",
    }.items():
        response = response.with_header(name, value)
    response = response.with_header("content-type", "application/json")
    _ = await response.get_body().write(
        json.dumps({"code": status_code, "message": message}, separators=(",", ":")).encode(),
    )
    return response
