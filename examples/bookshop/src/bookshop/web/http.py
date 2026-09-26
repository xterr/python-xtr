"""The request a route receives, and the response it returns."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import cast, final

__all__ = ["HttpError", "Request", "Response"]


@final
@dataclass(frozen=True, slots=True)
class Request:
    """One parsed HTTP request.

    Attributes:
        method: ``GET``, ``POST``, …
        path: The path, without the query string.
        query: The query string's parameters, last value wins.
        headers: Header names lower-cased.
        body: The raw body.
        path_params: What the route pattern captured, such as ``{"isbn": "978…"}``.
    """

    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict[str, str])
    headers: dict[str, str] = field(default_factory=dict[str, str])
    body: bytes = b""
    path_params: dict[str, str] = field(default_factory=dict[str, str])

    def json(self) -> dict[str, object]:
        """The body decoded as a JSON object.

        Raises:
            HttpError: 400 when the body is not a JSON object.
        """
        try:
            decoded = cast("object", json.loads(self.body or b"{}"))
        except json.JSONDecodeError as error:
            raise HttpError(HTTPStatus.BAD_REQUEST, f"invalid JSON: {error}") from error
        if not isinstance(decoded, dict):
            raise HttpError(HTTPStatus.BAD_REQUEST, "the body must be a JSON object")
        return {str(key): value for key, value in cast("dict[object, object]", decoded).items()}


@final
@dataclass(frozen=True, slots=True)
class Response:
    """What a route answers.

    Attributes:
        status: The status code.
        body: The encoded body.
        content_type: The ``Content-Type``.
    """

    status: HTTPStatus
    body: bytes
    content_type: str = "application/json"

    @classmethod
    def json(cls, payload: object, status: HTTPStatus = HTTPStatus.OK) -> Response:
        """A JSON response; values JSON cannot encode are written with ``str``."""
        return cls(status, json.dumps(payload, indent=2, default=str).encode() + b"\n")


@final
class HttpError(Exception):
    """A route's way of answering with an error status.

    Attributes:
        status: The status to answer with.
        detail: What went wrong.
    """

    def __init__(self, status: HTTPStatus, detail: str) -> None:
        """Answer ``status`` with ``detail``."""
        self.status = status
        self.detail = detail
        super().__init__(f"{status.value} {detail}")
