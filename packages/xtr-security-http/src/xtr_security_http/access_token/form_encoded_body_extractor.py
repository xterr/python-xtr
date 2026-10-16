"""An extractor that reads a bearer token from a form-encoded body."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast, final

from fastapi.security import HTTPBearer
from typing_extensions import override

from .access_token_extractor_interface import AccessTokenExtractorInterface

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["FormEncodedBodyExtractor"]

_FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"

#: The method whose body may carry a form, exactly as it travels on the wire.
#: RFC 9110 spells method names in upper case and matching them is
#: case-sensitive; a request that spells it any other way is not a form post.
_FORM_METHOD = "POST"

#: The largest form body read, so a bearer token in a body cannot be a memory
#: exhaustion vector; a larger body yields no token.
_MAX_BODY_SIZE = 64 * 1024


@final
class FormEncodedBodyExtractor(AccessTokenExtractorInterface):
    """Reads a token from a form field of an ``x-www-form-urlencoded`` body.

    RFC 6750 allows a bearer token in a form body; this reads the
    ``access_token`` field of one, when the request carries that content type.
    The body is read as the message the request arrived as — the read
    materialises it and its parsed side — and the token is read out of the
    parsed form, so no form-parsing dependency is needed. There is no
    dedicated OpenAPI scheme for a body-carried token, so it documents itself
    as the standard bearer scheme.

    Attributes:
        field_name: The form field the token is read from.
    """

    __slots__ = ("_bearer", "_field_name")

    def __init__(self, field_name: str = "access_token") -> None:
        """Build the extractor for the ``field_name`` form field."""
        self._field_name = field_name
        self._bearer = HTTPBearer(auto_error=False, bearerFormat="JWT", scheme_name="Bearer")

    @override
    async def extract_access_token(self, request: ServerRequestInterface) -> str | None:
        """Return the token in the form body, or ``None`` when it is absent.

        Only a ``POST`` whose content type names the form encoding is read —
        the one request a submitted form travels as. The body is read before
        the parsed form is asked for, the order a served request needs: the
        reading materialises both, and the parsed side answers behind it. A
        body that turns out larger than the 64 KiB cap yields no token — the
        cap weighs the bytes that actually arrived, never what a header
        promised — and so does a form whose field carries anything other than
        one text value; an endpoint behind the firewall then challenges rather
        than failing on the oversize or malformed body.
        """
        if request.get_method() != _FORM_METHOD:
            return None
        if not _is_form_content_type(request.get_header_line("Content-Type")):
            return None
        body = request.get_body()
        if len(await body.get_contents()) > _MAX_BODY_SIZE:
            return None
        parsed = request.get_parsed_body()
        if not isinstance(parsed, Mapping):
            return None
        value = cast("Mapping[str, object]", parsed).get(self._field_name)
        return value if isinstance(value, str) else None

    @override
    def scheme(self) -> SecurityBase:
        """Return the bearer scheme this extractor documents by."""
        return self._bearer


def _is_form_content_type(content_type: str) -> bool:
    """Tell whether a ``Content-Type`` header names the form encoding.

    The media type is read without its parameters and without regard to case,
    the same rules the kernel reads a content type by when it decides what a
    body parses into — so a body this check lets through is a body whose
    parsed side is the submitted form.
    """
    return content_type.partition(";")[0].strip().lower().startswith(_FORM_CONTENT_TYPE)
