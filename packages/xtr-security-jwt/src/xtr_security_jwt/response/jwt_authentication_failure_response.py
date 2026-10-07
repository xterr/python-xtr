"""The response a failed token authentication answers a request with."""

from __future__ import annotations

from typing import final

from starlette.responses import JSONResponse

__all__ = ["JwtAuthenticationFailureResponse"]


@final
class JwtAuthenticationFailureResponse(JSONResponse):
    """A ``401`` JSON response naming why a token was refused.

    Its body is ``{"code": <status>, "message": <message>}`` and it always
    carries a ``WWW-Authenticate: Bearer`` header, so a client is told both what
    went wrong and how to authenticate. It forbids every cache from keeping the
    refusal — ``Cache-Control: no-store`` and, for the caches that read only it,
    ``Pragma: no-cache`` — so a proxy cannot answer another caller's request with
    one principal's refusal. A listener may swap it for one of its own on the
    matching failure event.
    """

    def __init__(self, message: str = "Bad credentials", status_code: int = 401) -> None:
        """Answer with ``message`` at ``status_code``, challenging for a bearer token."""
        super().__init__(
            {"code": status_code, "message": message},
            status_code=status_code,
            headers={
                "WWW-Authenticate": "Bearer",
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )
