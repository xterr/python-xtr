"""An extractor that reads a bearer token from a form-encoded body."""

from __future__ import annotations

from typing import TYPE_CHECKING, final
from urllib.parse import parse_qs

from fastapi.security import HTTPBearer
from typing_extensions import override

from .access_token_extractor_interface import AccessTokenExtractorInterface

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase
    from starlette.requests import Request

__all__ = ["FormEncodedBodyExtractor"]

_FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


@final
class FormEncodedBodyExtractor(AccessTokenExtractorInterface):
    """Reads a token from a form field of an ``x-www-form-urlencoded`` body.

    RFC 6750 allows a bearer token in a form body; this reads the
    ``access_token`` field of one, when the request carries that content type.
    The body is parsed directly, so no form-parsing dependency is needed. There
    is no dedicated OpenAPI scheme for a body-carried token, so it documents
    itself as the standard bearer scheme.

    Attributes:
        field_name: The form field the token is read from.
    """

    __slots__ = ("_bearer", "_field_name")

    def __init__(self, field_name: str = "access_token") -> None:
        """Build the extractor for the ``field_name`` form field."""
        self._field_name = field_name
        self._bearer = HTTPBearer(auto_error=False, bearerFormat="JWT", scheme_name="Bearer")

    @override
    async def extract_access_token(self, request: Request) -> str | None:
        """Return the token in the form body, or ``None`` when it is absent."""
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith(_FORM_CONTENT_TYPE):
            return None
        body = await request.body()
        fields = parse_qs(body.decode("utf-8"))
        values = fields.get(self._field_name)
        return values[0] if values else None

    @override
    def scheme(self) -> SecurityBase:
        """Return the bearer scheme this extractor documents by."""
        return self._bearer
