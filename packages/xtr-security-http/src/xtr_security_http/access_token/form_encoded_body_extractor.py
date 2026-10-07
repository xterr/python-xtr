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

#: The largest form body read, so a bearer token in a body cannot be a memory
#: exhaustion vector; a larger declared or streamed body yields no token.
_MAX_BODY_SIZE = 64 * 1024


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
        """Return the token in the form body, or ``None`` when it is absent.

        A body whose ``content-length`` is above the 64 KiB cap — or, with no
        usable ``content-length``, one that streams past the cap — yields
        ``None``, as does a body that is not valid UTF-8; an endpoint behind the
        firewall then challenges rather than failing on the oversize or
        undecodable body.
        """
        content_type = request.headers.get("content-type", "")
        if not content_type.lower().startswith(_FORM_CONTENT_TYPE):
            return None
        body = await _read_capped(request)
        if body is None:
            return None
        try:
            text = body.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return None
        fields = parse_qs(text)
        values = fields.get(self._field_name)
        return values[0] if values else None

    @override
    def scheme(self) -> SecurityBase:
        """Return the bearer scheme this extractor documents by."""
        return self._bearer


async def _read_capped(request: Request) -> bytes | None:
    """Read the body of ``request`` up to the cap, or ``None`` when it is exceeded.

    A ``content-length`` the sender declares is only believed when it is a run
    of ASCII digits, which is all RFC 9110 allows: ``int`` would also take
    ``-1``, ``+5`` or a padded ``" 10 "``, and reading the body on the strength
    of such a header would leave the cap unenforced. A header is decoded as
    latin-1, so it can even carry a superscript ``²``, which counts as a digit
    yet is no number ``int`` can read. Anything else — absent, padded, signed or
    not a number — is read by streaming, which caps on what actually arrives
    rather than on what was promised. A body read by streaming is cached back on
    the request through :func:`_cache_body`, so an endpoint behind the firewall
    can still read its own body — ``await request.body()`` or a form parse —
    after the extractor has looked for a token.
    """
    declared = request.headers.get("content-length")
    if declared is not None and declared.isascii() and declared.isdigit():
        if int(declared) > _MAX_BODY_SIZE:
            return None
        return await request.body()
    collected = bytearray()
    async for chunk in request.stream():
        collected.extend(chunk)
        if len(collected) > _MAX_BODY_SIZE:
            return None
    body = bytes(collected)
    _cache_body(request, body)
    return body


def _cache_body(request: Request, body: bytes) -> None:
    """Hand the streamed ``body`` back to Starlette as the request's cached body.

    ``request.stream()`` consumes the body once; without this, a later
    ``await request.body()`` from the endpoint raises ``RuntimeError: Stream
    consumed``. Starlette's own ``body()`` caches into the ``_body`` attribute
    and every later ``stream()``/``body()`` serves from it, so setting that
    attribute is how a value read ahead of the route is made available to it.
    This is the one private attribute that mechanism exposes; it is set in this
    single documented place.
    """
    # SLF001/reportPrivateUsage: Starlette's own body() caches into this same
    # attribute; setting it is the supported re-read path. See the docstring.
    request._body = body  # noqa: SLF001 # pyright: ignore[reportPrivateUsage]
